import os, sys, json, requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("MODEL_API_KEY")
BASE = "https://api.meta.ai/v1"
HEAD = {"Authorization": f"Bearer {KEY}"}

PROMPT = ("Read this handwritten ledger. Return ONLY a JSON list of rows, "
          "each with item, quantity (number) and amount (number, in rand). No other text.")

def check(r):
    if not r.ok:
        print("ERROR", r.status_code, r.text)
        sys.exit(1)
    return r.json()

def upload(path):
    with open(path, "rb") as f:
        r = requests.post(f"{BASE}/files", headers=HEAD,
                          data={"purpose": "user_data"}, files={"file": f})
    return check(r)["id"]

def extract(file_id):
    body = {
        "model": "muse-spark-1.3",
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": PROMPT},
            {"type": "input_image", "file_id": file_id}]}],
        "stream": False,
        "max_output_tokens": 4000,
    }
    r = requests.post(f"{BASE}/responses",
                      headers={**HEAD, "Content-Type": "application/json"}, json=body)
    return check(r)

if __name__ == "__main__":
    fid = upload(sys.argv[1])
    print("file id:", fid)
    print(json.dumps(extract(fid), indent=2))
