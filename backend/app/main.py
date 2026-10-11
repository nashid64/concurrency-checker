from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException

from .config import load_settings
from .llm_detector import LLMError
from .model_detector import ModelNotAvailable
from .schemas import AnalyzeRequest, AnalyzeResponse
from .service import Analyzer

settings = load_settings()
analyzer = Analyzer(settings)

app = FastAPI(title="Concurrency Checker API", version="1.0.0")


def check_key(x_api_key: Optional[str] = Header(default=None)):
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Missing or wrong X-API-Key")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "default_mode": settings.detector_mode,
        "llm_configured": bool(settings.llm_api_key),
        "llm_model": settings.llm_model,
        "model_available": analyzer.model.available(),
        "model_loaded": analyzer.model.loaded,
        "auth_required": bool(settings.api_key),
    }


@app.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(check_key)])
def analyze(req: AnalyzeRequest):
    if len(req.code) > settings.max_code_chars:
        raise HTTPException(status_code=413, detail=f"Code too large ({len(req.code)} chars > {settings.max_code_chars})")
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="Empty code")
    try:
        return analyzer.analyze(req)
    except LLMError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    except ModelNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
