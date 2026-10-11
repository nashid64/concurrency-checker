"""Send every samples/*.java file to the running backend and print the result.
Usage (backend must be running):  python scripts/smoke_test.py [http://127.0.0.1:8000] [api_key]"""
import json
import sys
import urllib.request
from pathlib import Path

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
key = sys.argv[2] if len(sys.argv) > 2 else ""
samples = sorted((Path(__file__).resolve().parents[2] / "samples").glob("*.java"))

def call(path, body=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

print("HEALTH:", call("/health"))
for f in samples:
    res = call("/analyze", {"code": f.read_text(encoding="utf-8"), "language": "java", "filename": f.name})
    print(f"\n== {f.name}: verdict={res['verdict']} detector={res['detector']} ({res['elapsed_ms']} ms)")
    for b in res["bugs"]:
        print(f"   line {b['line']}: [{b['type']}] {b['message']}")
