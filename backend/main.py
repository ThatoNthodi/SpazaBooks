import os, re, json, secrets
from datetime import date
from uuid import UUID, uuid4
from typing import List, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

BASE = "https://api.meta.ai/v1"
MODEL = "muse-spark-1.3"
MAX_IMAGE_BYTES = 8 * 1024 * 1024

app = FastAPI(title="Spaza Books API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LedgerRow(BaseModel):
    date: str
    description: str
    type: str  # "income" or "expense"
    amount: float
    credit_customer: Optional[str] = None


PROMPT = (
    "Read this handwritten ledger. Return ONLY a JSON list, no other text. "
    "Each element has: item (string), quantity (number), amount (number, rand), "
    "kind (one of sale, expense, credit), customer (string or null, only for credit), "
    "date (string as written on the page, or null). "
    "Do not invent rows. Do not guess illegible values: use null for them."
)


def model_key() -> str:
    key = (os.getenv("MODEL_API_KEY") or "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="MODEL_API_KEY is not set.")
    return key


def get_supabase():
    from supabase import create_client
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase settings are missing.")
    return create_client(url, key)


def clean_date(value):
    """Turn '25 | 10 | 2026' or '25-10-2026' into '25/10/2026'."""
    if not value:
        return None
    s = re.sub(r"\s+", "", str(value))
    return re.sub(r"[|\-.]", "/", s)


def check_access(x_access_code: str = Header(default="")):
    expected = os.getenv("ACCESS_CODE")
    if expected and not secrets.compare_digest(x_access_code.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Access code required.")


@app.get("/")
def read_root():
    return {"status": "Spaza Books API is running", "hackathon": "Meta Global AI Developer Hackathon"}


@app.post("/api/extract", dependencies=[Depends(check_access)])
async def extract_rows(file: UploadFile = File(...)):
    """Read a photo of a handwritten ledger and return rows to be confirmed."""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")
    contents = await file.read()
    if not contents or len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image is empty or larger than 8 MB.")

    headers = {"Authorization": f"Bearer {model_key()}"}
    try:
        up = requests.post(
            f"{BASE}/files",
            headers=headers,
            data={"purpose": "user_data"},
            files={"file": (file.filename or "page.jpg", contents, file.content_type)},
            timeout=60,
        )
        up.raise_for_status()
        file_id = up.json()["id"]

        resp = requests.post(
            f"{BASE}/responses",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": PROMPT},
                    {"type": "input_image", "file_id": file_id},
                ]}],
                "stream": False,
                "max_output_tokens": 4000,
                "temperature": 0,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(
            c["text"]
            for o in data["output"] if o["type"] == "message"
            for c in o["content"] if c["type"] == "output_text"
        )
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        raw_rows = json.loads(text)
        if not isinstance(raw_rows, list):
            raise ValueError("Expected a JSON list.")
    except requests.RequestException as e:
        resp_obj = getattr(e, "response", None)
        print("META REQUEST FAILED:", type(e).__name__,
              getattr(resp_obj, "status_code", None),
              (getattr(resp_obj, "text", "") or str(e))[:300], flush=True)
        raise HTTPException(status_code=502, detail="The Muse Spark request failed. Try again.")
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="The model returned an unreadable answer. Try again.")

    today = date.today().strftime("%d/%m/%Y")
    rows = []
    for r in raw_rows:
        try:
            kind = str(r.get("kind", "sale")).lower()
            qty = r.get("quantity")
            qty_text = f" {int(qty)}" if isinstance(qty, (int, float)) and float(qty).is_integer() else (f" {qty}" if qty else "")
            rows.append({
                "date": clean_date(r.get("date")) or today,
                "description": f"{r.get('item', '').strip()}{qty_text}".strip(),
                "type": "expense" if kind == "expense" else "income",
                "amount": float(r.get("amount") or 0),
                "credit_customer": r.get("customer") if kind == "credit" else None,
                "needs_check": r.get("amount") is None or r.get("item") in (None, ""),
            })
        except (AttributeError, ValueError, TypeError):
            continue

    return {"ledger_batch_id": str(uuid4()), "rows": rows}


@app.post("/api/store", dependencies=[Depends(check_access)])
async def store_ledger_rows(payload: dict):
    """Save confirmed transactions once per ledger batch."""
    try:
        batch_id = UUID(payload["ledger_batch_id"])
        rows = payload["rows"]
        if not isinstance(rows, list) or not rows:
            raise HTTPException(status_code=400, detail="At least one transaction is required.")

        to_insert = []
        for index, item in enumerate(rows):
            row = LedgerRow.model_validate(item)
            to_insert.append({**row.model_dump(), "ledger_batch_id": str(batch_id), "ledger_batch_row": index})

        response = get_supabase().table("ledgers").insert(to_insert).execute()
        return {"status": "success", "inserted_count": len(response.data), "data": response.data}

    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "ledgers_batch_row_unique" in msg or "23505" in msg:
            raise HTTPException(status_code=409, detail="This ledger batch has already been saved.")
        raise HTTPException(status_code=500, detail="Could not save transactions to the database.")


def _parse_date(s):
    from datetime import datetime
    s = str(s or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m"):
        try:
            d = datetime.strptime(s, fmt)
            if fmt == "%d/%m":
                d = d.replace(year=date.today().year)
            return d.date()
        except ValueError:
            continue
    return None


def _item_name(description):
    name = re.sub(r"[\s\d.]+(pck|pk|pack|kg|l)?$", "", str(description or ""), flags=re.I).strip()
    return name or str(description or "")


@app.get("/api/summary", dependencies=[Depends(check_access)])
def weekly_summary(days: int = 7):
    """Plain-language summary of recent sales. Numbers come from code, wording from the model."""
    from datetime import timedelta
    from collections import defaultdict

    days = max(1, min(days, 90))
    since = date.today() - timedelta(days=days)
    rows = get_supabase().table("ledgers").select("*").execute().data or []

    sales = expenses = on_credit = 0.0
    by_item, by_day, debtors = defaultdict(float), defaultdict(float), defaultdict(float)
    counted = 0
    for r in rows:
        d = _parse_date(r.get("date"))
        if not d or d < since:
            continue
        amt = float(r.get("amount") or 0)
        counted += 1
        if r.get("type") == "expense":
            expenses += amt
        else:
            sales += amt
            by_item[_item_name(r.get("description"))] += amt
            by_day[d.isoformat()] += amt
            if r.get("credit_customer"):
                on_credit += amt
                debtors[r["credit_customer"]] += amt

    facts = {
        "period_days": days,
        "entries_counted": counted,
        "total_sales_rand": round(sales, 2),
        "total_expenses_rand": round(expenses, 2),
        "owed_on_credit_rand": round(on_credit, 2),
        "owed_by": {k: round(v, 2) for k, v in debtors.items()},
        "best_seller": max(by_item, key=by_item.get) if by_item else None,
        "best_seller_rand": round(max(by_item.values()), 2) if by_item else 0,
        "busiest_day": max(by_day, key=by_day.get) if by_day else None,
        "busiest_day_rand": round(max(by_day.values()), 2) if by_day else 0,
    }

    summary = None
    if counted:
        prompt = (
            "You help a small spaza shop owner understand their week. Using ONLY these figures "
            "(South African rand), write 3 short, plain-English sentences: how the week went, "
            "the best seller, and one practical suggestion. Do not invent any numbers.\n"
            + json.dumps(facts)
        )
        try:
            resp = requests.post(
                f"{BASE}/responses",
                headers={"Authorization": f"Bearer {model_key()}", "Content-Type": "application/json"},
                json={"model": MODEL,
                      "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
                      "stream": False, "max_output_tokens": 8000, "temperature": 0,
                      "reasoning": {"effort": "medium"}},
                timeout=120,
            )
            resp.raise_for_status()
            summary = "".join(
                c["text"] for o in resp.json()["output"] if o["type"] == "message"
                for c in o["content"] if c["type"] == "output_text"
            ).strip()
        except Exception:
            summary = None

    ai_written = bool(summary)
    if counted and not summary:
        parts = [f"You sold R{facts['total_sales_rand']:.0f} over the last {days} days"]
        if facts["best_seller"]:
            parts.append(f"your best seller was {facts['best_seller']}")
        if facts["owed_on_credit_rand"]:
            parts.append(f"customers still owe you R{facts['owed_on_credit_rand']:.0f}")
        summary = ", and ".join(parts) + "."

    return {"facts": facts, "summary": summary, "ai_written": ai_written}
