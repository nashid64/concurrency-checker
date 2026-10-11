import time
from typing import Optional

from . import mock_detector
from .common import guess_line, normalize_type, verdict_from_types
from .config import Settings
from .llm_detector import LLMDetector, LLMError
from .model_detector import ModelDetector, ModelNotAvailable
from .schemas import AnalyzeRequest, AnalyzeResponse, Bug

VALID_MODES = {"mock", "llm", "model", "hybrid"}

MODEL_MESSAGES = {
    "race_condition": "The local model thinks this file contains a race condition (unsynchronized shared state).",
    "deadlock": "The local model thinks this file can deadlock (inconsistent lock order or lock cycle).",
    "concurrency_issue": "The local model thinks this file has a thread-safety problem (visibility, atomicity, lock leak, wait/notify ...).",
}


class Analyzer:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.llm = LLMDetector(cfg)
        self.model = ModelDetector(cfg)

    def resolve_mode(self, requested: Optional[str]) -> str:
        mode = (requested or "").strip().lower()
        if mode and self.cfg.allow_mode_override and mode in VALID_MODES:
            return mode
        return self.cfg.detector_mode if self.cfg.detector_mode in VALID_MODES else "mock"

    def _model_bugs(self, code: str):
        label, conf, _ = self.model.predict(code)
        if label == "safe":
            return label, conf, []
        bug = Bug(
            type=label,
            line=guess_line(code),
            severity="error" if label == "deadlock" else "warning",
            message=MODEL_MESSAGES.get(label, "Possible concurrency problem.") + " (file-level result, line is approximate)",
            suggestion=None,
        )
        return label, conf, [bug]

    def analyze(self, req: AnalyzeRequest) -> AnalyzeResponse:
        t0 = time.time()
        mode = self.resolve_mode(req.mode)
        note = None
        confidence = None
        if mode == "mock":
            bugs = [Bug(**b) for b in mock_detector.analyze(req.code)]
            note = "mock mode: simple demo rules, not a real analysis"
        elif mode == "llm":
            bugs = [Bug(**b) for b in self.llm.analyze(req.code, req.filename)]
        elif mode == "model":
            _, confidence, bugs = self._model_bugs(req.code)
        else:  # hybrid
            label, confidence, model_bugs = self._model_bugs(req.code)
            if label == "safe" and confidence >= self.cfg.hybrid_safe_threshold:
                bugs = []
                note = "hybrid: local model is confident the file is safe (LLM not called)"
            else:
                try:
                    bugs = [Bug(**b) for b in self.llm.analyze(req.code, req.filename)]
                    note = "hybrid: local model flagged / was unsure, LLM gave line-level result"
                except LLMError as exc:
                    bugs = model_bugs
                    note = f"hybrid: LLM unavailable ({exc.message}); showing local model result"
        types = [normalize_type(b.type) for b in bugs]
        return AnalyzeResponse(
            bugs=bugs,
            verdict=verdict_from_types(types),
            confidence=confidence,
            detector=mode,
            elapsed_ms=int((time.time() - t0) * 1000),
            note=note,
        )
