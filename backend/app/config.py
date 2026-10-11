"""Settings read from environment variables / backend/.env"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _bool(value: str, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    detector_mode: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout: float
    model_dir: str
    hybrid_safe_threshold: float
    max_code_chars: int
    api_key: str
    allow_mode_override: bool


def load_settings() -> Settings:
    model_dir = os.getenv("MODEL_DIR", "./models/concurrency-model")
    if not os.path.isabs(model_dir):
        model_dir = str((BACKEND_DIR / model_dir).resolve())
    return Settings(
        detector_mode=os.getenv("DETECTOR_MODE", "mock").strip().lower(),
        llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        llm_model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
        llm_timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        model_dir=model_dir,
        hybrid_safe_threshold=float(os.getenv("HYBRID_SAFE_THRESHOLD", "0.90")),
        max_code_chars=int(os.getenv("MAX_CODE_CHARS", "60000")),
        api_key=os.getenv("API_KEY", ""),
        allow_mode_override=_bool(os.getenv("ALLOW_MODE_OVERRIDE"), True),
    )
