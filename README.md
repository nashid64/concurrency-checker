# Concurrency Checker

A VS Code extension that finds concurrency bugs (race conditions, deadlocks, thread-safety problems) in **Java** code,
backed by a Python (FastAPI) service that can use

| mode | what it uses | needs |
|---|---|---|
| `mock` | tiny rule-based demo | nothing (good for the first test) |
| `llm` | Gemini free tier (OpenAI-compatible API) or any OpenAI-compatible LLM | API key |
| `model` | your own fine-tuned CodeBERT classifier | `torch`, `transformers`, trained model |
| `hybrid` | local model first, LLM only when the model is unsure or finds a bug | both |

```
VS Code extension (TypeScript)  --HTTP POST /analyze-->  FastAPI backend  -->  mock | LLM | local model
```

## Folders
- `extension/`  VS Code extension (TypeScript)
- `backend/`    FastAPI service (`app/`), tests, Dockerfile
- `training/`   `train.py` - fine-tune the local model (use Google Colab GPU)
- `evaluation/` scripts that send the test CSVs to the backend and produce metrics + graphs
- `data/`       dataset (2000 synthetic + 38 Juliet samples) and test splits
- `samples/`    three Java files for trying the extension

## Quick start (Windows PowerShell)
```powershell
# 1) backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --port 8000

# 2) extension (new terminal)
cd extension
npm install
npm run compile
code .          # then press F5
```
Full step-by-step guide (Bangla): see the PDF that came with this project.

## Data notes
`label4`: `safe | race_condition | deadlock | concurrency_issue`. The 2000 synthetic samples come from 21 code templates,
so results on them are optimistic; the 38 Juliet samples are the independent check.
