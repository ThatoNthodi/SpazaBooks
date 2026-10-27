import csv, re, difflib, requests

API = "http://127.0.0.1:8000/api/extract"
DATES = {1: "21/10/2026", 2: "22/10/2026", 3: "25/10/2026", 4: "24/10/2026",
         5: "23/10/2026", 6: "27/10/2026", 7: "27/10/2026"}


def split(desc):
    m = re.match(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*(?:pck|pk|pack)?$", str(desc).strip(), re.I)
    return (m.group(1), float(m.group(2))) if m else (str(desc), None)


def norm(s):
    return re.sub(r"\b(pack|pk|pck)\b", "", s.lower()).strip()


def same(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() >= 0.8


key = {}
with open("spaza-test/answers.csv", newline="") as f:
    for r in csv.DictReader(f):
        key.setdefault(int(r["page"]), []).append(r)

fields = ["item", "quantity", "amount", "type", "credit", "date"]
ok = {f: 0 for f in fields}
total = rows_ok = rows_all = 0

for page in sorted(key):
    with open(f"spaza-test/page{page}.jpg", "rb") as fh:
        resp = requests.post(API, files={"file": (f"page{page}.jpg", fh, "image/jpeg")}, timeout=180)
    if not resp.ok:
        print(f"page {page}: ERROR {resp.status_code} {resp.text[:150]}")
        continue
    got = resp.json()["rows"]
    if len(got) != len(key[page]):
        print(f"page {page}: expected {len(key[page])} rows, got {len(got)}")
    for i, e in enumerate(key[page]):
        g = got[i] if i < len(got) else {}
        name, qty = split(g.get("description", ""))
        want_type = "expense" if e["kind"] == "expense" else "income"
        checks = {
            "item": same(e["item"], name),
            "quantity": qty is not None and qty == float(e["quantity"]),
            "amount": float(g.get("amount") or -1) == float(e["amount"]),
            "type": g.get("type") == want_type,
            "credit": bool(g.get("credit_customer")) == (e["kind"] == "credit"),
            "date": g.get("date") == DATES[page],
        }
        rows_all += 1
        rows_ok += all(checks.values())
        for k, v in checks.items():
            ok[k] += v
        if not all(checks.values()):
            bad = [k for k, v in checks.items() if not v]
            print(f"page {page} row {e['row']}: wrong {bad} | expected {e['item']}, {e['quantity']}, R{e['amount']}, {e['kind']} | got {g.get('description')}, R{g.get('amount')}, {g.get('type')}, {g.get('credit_customer')}, {g.get('date')}")

print(f"\nRows with every field correct: {rows_ok}/{rows_all}")
for k in fields:
    print(f"  {k}: {ok[k]}/{rows_all}")
