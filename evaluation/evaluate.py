"""Send each test sample to the backend /analyze endpoint and save predictions (resumable).
Run from the project root folder."""
import argparse, json, os, re, time
import pandas as pd, requests

p = argparse.ArgumentParser()
p.add_argument("--data", required=True, help="CSV, e.g. data/test_synthetic_400.csv")
p.add_argument("--out", required=True, help="output jsonl, e.g. results/synthetic.jsonl")
p.add_argument("--url", default="http://localhost:8000/analyze")
p.add_argument("--field", default="code", help="JSON key your endpoint expects the code in")
p.add_argument("--extra", default="{}", help='extra JSON fields, e.g. \'{"language":"java"}\'')
p.add_argument("--limit", type=int, default=0, help="only first N rows (0 = all)")
p.add_argument("--header", default="", help='extra header as KEY=VALUE, e.g. X-API-Key=secret')
p.add_argument("--sleep", type=float, default=4.0, help="seconds between calls (free-tier rate limit)")
p.add_argument("--probe", action="store_true", help="send ONE sample and print the raw response")
a = p.parse_args()

df = pd.read_csv(a.data)
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
if a.limit: df = df.head(a.limit)
if a.probe: df = df.head(1)

done = set()
if os.path.exists(a.out) and not a.probe:
    done = {json.loads(l)["uid"] for l in open(a.out, encoding="utf-8")}

def call(code):
    body = {a.field: code, **json.loads(a.extra)}
    hdr = dict([a.header.split('=', 1)]) if a.header else {}
    r = requests.post(a.url, json=body, headers=hdr, timeout=180)
    r.raise_for_status()
    return r.json()

for i, row in df.iterrows():
    if row.uid in done: continue
    try:
        resp, err = call(row.code), None
    except Exception as e:
        resp, err = None, str(e)
    if a.probe:
        print("ERROR:" if err else "RAW RESPONSE:", err or json.dumps(resp, indent=2, ensure_ascii=False)); break
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(json.dumps({"uid": row.uid, "response": resp, "error": err}, ensure_ascii=False) + "\n")
    print(f"[{i+1}/{len(df)}] {row.uid} -> {'ERR ' + err[:60] if err else 'ok'}")
    time.sleep(a.sleep)
