# Concurrency Checker

A VS Code extension that finds concurrency bugs (race conditions, deadlocks, thread-safety problems) in **Java** code,
backed by a Python (FastAPI) service that can use

| mode | what it uses | needs |
|---|---|---|
| `mock` | tiny rule-based demo | nothing (good for the first test) |
| `llm` | Gemini free tier (OpenAI-compatible API) or any OpenAI-compatible LLM | API key |
| `model` | our own fine-tuned CodeBERT classifier | `torch`, `transformers`, trained model |
| `hybrid` | local model first, LLM only when the model is unsure or finds a bug | both |

```
VS Code extension (TypeScript)  --HTTP POST /analyze-->  FastAPI backend  -->  mock | LLM | local model
```

## Folders
- `extension/`  VS Code extension (TypeScript)
- `backend/`    FastAPI service (`app/`), tests, Dockerfile
- `training/`   `train.py` - fine-tune the local model (use Google Colab GPU)
- `evaluation/` scripts that send the test CSVs to the backend and produce metrics + graphs
- `results/`, `graphs/`  output of the evaluation scripts
- `data/`       dataset (2000 synthetic + 38 Juliet samples) and test splits
- `samples/`    three Java files for trying the extension
- `launcher.pyw`  small window with Run / Stop buttons for the backend

## Setup (Windows)

### 1. Get the code
```powershell
git clone https://github.com/nashid64/concurrency-checker.git
cd concurrency-checker
```

### 2. Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-model.txt     # torch + transformers (needed for model / hybrid mode)
copy .env.example .env
```
If `torch` does not install, use Python 3.12 or 3.13 for the virtual environment.

### 3. Download the local model
The model weights (about 476 MB) are not in git. Download the model folder from Google Drive:

**https://drive.google.com/drive/folders/1tWeX_kFnNhY7Nxyq7jRPsHNZbWInfWwz?usp=sharing**

Put these four files **directly** inside `backend/models/concurrency-model/`:

```
backend/models/concurrency-model/
    config.json
    model.safetensors
    tokenizer.json
    tokenizer_config.json
```
(If Drive gives you a zip, unzip it first. Make sure the files are not inside an extra sub-folder.)

### 4. Edit `backend/.env`
Open `backend/.env` and set at least:
```
DETECTOR_MODE=hybrid
LLM_API_KEY=<your Gemini API key from Google AI Studio>
LLM_MODEL=<a current Flash / Flash-Lite model name>
```
Run `python scripts/list_models.py` (inside `backend`, venv active) to see the model names your key can use.
Never commit `.env`; it is git-ignored.

### 5. Start the backend
With the terminal (inside `backend`, venv active):
```powershell
uvicorn app.main:app --port 8000
```
or with buttons: from the project root run
```powershell
backend\.venv\Scripts\pythonw.exe launcher.pyw
```
and press **Run** (**Stop** stops the server). The window shows the exact command and the server output.

Check it: open <http://127.0.0.1:8000/health>. You should see `"default_mode":"hybrid"` and `"model_available":true`
(`model_loaded` becomes `true` after the first analysis; the model loads on first use).

### 6. Extension
```powershell
cd extension
npm install
npm run compile
code .          # then press F5
```
In the new VS Code window open a `.java` file from `samples/` and save it. Problems appear as red underlines.
You can pick the mode from VS Code settings: `concurrencyChecker.detectorMode`
(`server-default`, `mock`, `llm`, `model`, `hybrid`).

Full step-by-step guide (Bangla): see the PDF that came with this project.

## Evaluation (optional)
Run from the project root with the backend running (Command Prompt):
```bat
python evaluation/evaluate.py --data data/test_juliet_38.csv --out results/juliet_model.jsonl --extra "{\"mode\":\"model\"}" --sleep 0
python evaluation/metrics_graphs.py --data data/test_juliet_38.csv --pred results/juliet_model.jsonl --name juliet_model
```
Use `{\"mode\":\"llm\"}` or `{\"mode\":\"hybrid\"}` for the other modes (keep the default `--sleep 4` for the free LLM tier).

## Data notes
`label4`: `safe | race_condition | deadlock | concurrency_issue`. The 2000 synthetic samples come from 21 code templates,
so results on them are optimistic; the 38 Juliet samples are the independent check.

## Notes
- The shipped local model is a small binary classifier (`safe` / `concurrency_issue`) trained on a few hundred samples, so in
  `hybrid` mode the LLM decides most cases. Bug type, line and fix come from the LLM.
- Part of `data/test_juliet_38.csv` comes from the same Juliet files used to train that model, so model-only results on it are optimistic.
