"""Print the model names your API key can use (to fill LLM_MODEL in .env).  Run from the backend folder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import load_settings  # noqa: E402
from openai import OpenAI  # noqa: E402

cfg = load_settings()
if not cfg.llm_api_key:
    sys.exit("LLM_API_KEY is empty in backend/.env")
client = OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url)
for m in client.models.list():
    print(m.id)
