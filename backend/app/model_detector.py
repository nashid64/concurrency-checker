"""Local fine-tuned classifier (CodeBERT etc.) trained with training/train.py"""
import os
from typing import Dict, Tuple

from .config import Settings


class ModelNotAvailable(Exception):
    pass


class ModelDetector:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self._tok = None
        self._model = None
        self._torch = None
        self._device = "cpu"

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def available(self) -> bool:
        return os.path.isfile(os.path.join(self.cfg.model_dir, "config.json"))

    def _load(self):
        if self._model is not None:
            return
        if not self.available():
            raise ModelNotAvailable(
                f"Model folder not found: {self.cfg.model_dir}. Train it (training/train.py) and copy it to backend/models/concurrency-model."
            )
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ModelNotAvailable(
                "torch/transformers are not installed. Run: pip install -r requirements-model.txt"
            ) from exc
        self._torch = torch
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._tok = AutoTokenizer.from_pretrained(self.cfg.model_dir)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.cfg.model_dir).to(self._device)
        self._model.eval()

    def predict(self, code: str) -> Tuple[str, float, Dict[str, float]]:
        self._load()
        torch = self._torch
        enc = self._tok(code, truncation=True, max_length=512, return_tensors="pt").to(self._device)
        with torch.no_grad():
            logits = self._model(**enc).logits[0]
        probs = torch.softmax(logits, dim=-1).cpu().tolist()
        id2label = self._model.config.id2label
        scores = {str(id2label[i]): float(p) for i, p in enumerate(probs)}
        label = max(scores, key=scores.get)
        return label, scores[label], scores
