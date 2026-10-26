import csv, json, re, difflib, requests
from extract_test import BASE, HEAD, PROMPT, check, upload

def run(file_id):
    body = {"model": "muse-spark-1.3",
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": PROMPT},
                {"type": "input_image", "file_id": file_id}]}],
            "stream": False, "max_output_tokens": 4000, "temperature": 0}
    r = requests.post(f"{BASE}/responses",
                      headers={**HEAD, "Content-Type": "application/json"}, json=body)
    data = check(r)
    text = "".join(c["text"] for o in data["output"] if o["type"] == "message"
                   for c in o["content"] if c["type"] == "output_text")
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text), data["usage"]

def norm(s):
    return re.sub(r"\b(pack|pk|pck)\b", "", str(s).lower()).strip()

def same_item(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() >= 0.8

key = {}
with open("spaza-test/answers.csv", newline="") as f:
    for r in csv.DictReader(f):
        key.setdefault(int(r["page"]), []).append(r)

rows_ok = rows_all = fields_ok = fields_all = 0
results, tokens = {}, 0
for page in sorted(key):
    fid = upload(f"spaza-test/page{page}.jpg")
    try:
        got, usage = run(fid)
    except Exception as e:
        print(f"page {page}: could not read reply ({e})")
        continue
    tokens += usage["total_tokens"]
    results[page] = got
    exp = key[page]
    if len(got) != len(exp):
        print(f"page {page}: expected {len(exp)} rows, got {len(got)}")
    for i, e in enumerate(exp):
        rows_all += 1
        fields_all += 3
        g = got[i] if i < len(got) else {}
        ok = [same_item(e["item"], g.get("item", "")),
              float(e["quantity"]) == float(g.get("quantity", -1)),
              float(e["amount"]) == float(g.get("amount", -1))]
        fields_ok += sum(ok)
        rows_ok += all(ok)
        if not all(ok):
            print(f"page {page} row {e['row']}: expected {e['item']}, {e['quantity']}, R{e['amount']} | got {g}")

print(f"\nRows fully correct: {rows_ok}/{rows_all}")
print(f"Fields correct: {fields_ok}/{fields_all}")
print(f"Total tokens used: {tokens}")
json.dump(results, open("spaza-test/results.json", "w"), indent=2)
