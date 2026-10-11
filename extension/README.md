# Concurrency Checker

Finds concurrency bugs in Java code (race conditions, deadlocks, thread-safety problems) and shows them as
squiggly underlines in VS Code. The analysis is done by a backend you run yourself (see the main project README).

## Use
1. Start the backend (`uvicorn app.main:app --port 8000` in the `backend` folder).
2. Open a `.java` file and save it (or run **Concurrency Checker: Analyze Current File**).
3. Problems appear in the editor and in the Problems panel.

## Settings
| Setting | Meaning |
|---|---|
| `concurrencyChecker.backendUrl` | Backend address, default `http://127.0.0.1:8000` |
| `concurrencyChecker.apiKey` | Optional `X-API-Key` header value |
| `concurrencyChecker.detectorMode` | `server-default`, `mock`, `llm`, `model`, `hybrid` |
| `concurrencyChecker.analyzeOnSave` | Analyze automatically on save |
| `concurrencyChecker.timeoutSeconds` | Request timeout |
| `concurrencyChecker.maxFileChars` | Largest file that is sent |

Privacy: the full text of the analyzed Java file is sent to the backend you configure, and (in `llm`/`hybrid` mode) from there to the LLM provider.
