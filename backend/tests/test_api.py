import os
import sys
from pathlib import Path

os.environ["DETECTOR_MODE"] = "mock"
os.environ["API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402

client = TestClient(main.app)
SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def read(name):
    return (SAMPLES / name).read_text(encoding="utf-8")


def analyze(code, **extra):
    return client.post("/analyze", json={"code": code, "language": "java", **extra})


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_deadlock_detected():
    r = analyze(read("DeadlockDemo.java"))
    assert r.status_code == 200
    assert r.json()["verdict"] == "deadlock"
    assert r.json()["bugs"][0]["line"] >= 1


def test_race_detected():
    r = analyze(read("RaceDemo.java"))
    assert r.json()["verdict"] == "race_condition"


def test_safe_code_has_no_bugs():
    r = analyze(read("SafeDemo.java"))
    assert r.json()["verdict"] == "safe"
    assert r.json()["bugs"] == []


def test_empty_and_too_large():
    assert analyze("   ").status_code == 400
    assert analyze("x" * (main.settings.max_code_chars + 1)).status_code == 413


def test_model_mode_without_model_gives_503():
    r = analyze(read("RaceDemo.java"), mode="model")
    assert r.status_code == 503


def test_llm_mode_without_key_gives_error():
    r = analyze(read("RaceDemo.java"), mode="llm")
    assert r.status_code == 500 and "LLM_API_KEY" in r.json()["detail"]


def test_api_key_enforced():
    object.__setattr__(main.settings, "api_key", "secret")
    try:
        assert analyze("class A {}").status_code == 401
        ok = client.post("/analyze", json={"code": "class A {}"}, headers={"X-API-Key": "secret"})
        assert ok.status_code == 200
    finally:
        object.__setattr__(main.settings, "api_key", "")
