/** Pure helper code (does not import "vscode") so it can be unit-tested with plain Node. */

export type Severity = 'error' | 'warning' | 'info';

export interface Bug {
  type: string;
  line: number; // 1-based
  endLine: number; // 1-based, >= line
  severity: Severity;
  message: string;
  suggestion?: string;
}

export interface AnalyzeResult {
  bugs: Bug[];
  verdict: string;
  detector: string;
  confidence?: number;
  elapsedMs?: number;
  note?: string;
}

function toInt(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : parseInt(String(value), 10);
  return Number.isFinite(n) ? Math.trunc(n) : fallback;
}

function toSeverity(value: unknown, type: string): Severity {
  const v = String(value ?? '').toLowerCase();
  if (v === 'error' || v === 'warning' || v === 'info') {
    return v;
  }
  return type === 'deadlock' ? 'error' : 'warning';
}

/** Turns whatever the backend returned into a safe, well-formed result. */
export function normalizeResponse(raw: unknown, lineCount: number): AnalyzeResult {
  const obj = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const list = Array.isArray(obj.bugs) ? obj.bugs : [];
  const maxLine = Math.max(lineCount, 1);
  const bugs: Bug[] = [];
  for (const item of list) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const b = item as Record<string, unknown>;
    const type = String(b.type ?? 'concurrency_issue');
    const line = Math.min(Math.max(toInt(b.line, 1), 1), maxLine);
    const endLine = Math.min(Math.max(toInt(b.end_line, line), line), maxLine);
    bugs.push({
      type,
      line,
      endLine,
      severity: toSeverity(b.severity, type),
      message: String(b.message ?? 'Possible concurrency problem.'),
      suggestion: b.suggestion ? String(b.suggestion) : undefined,
    });
  }
  return {
    bugs,
    verdict: String(obj.verdict ?? (bugs.length ? 'concurrency_issue' : 'safe')),
    detector: String(obj.detector ?? 'unknown'),
    confidence: typeof obj.confidence === 'number' ? obj.confidence : undefined,
    elapsedMs: typeof obj.elapsed_ms === 'number' ? obj.elapsed_ms : undefined,
    note: obj.note ? String(obj.note) : undefined,
  };
}

export function diagnosticText(b: Bug): string {
  const label = b.type.replace(/_/g, ' ');
  return b.suggestion ? `[${label}] ${b.message}\nFix: ${b.suggestion}` : `[${label}] ${b.message}`;
}

/** Friendly explanation for network errors thrown by fetch(). */
export function explainNetworkError(err: unknown, url: string): string {
  const e = err as { name?: string; message?: string; cause?: { code?: string } };
  if (e?.name === 'AbortError') {
    return 'The backend did not answer in time (timeout). Increase concurrencyChecker.timeoutSeconds or check the backend log.';
  }
  const code = e?.cause?.code;
  if (code === 'ECONNREFUSED') {
    return `Cannot connect to ${url}. Is the backend running? Start it with: uvicorn app.main:app --port 8000 (inside the backend folder).`;
  }
  if (code === 'ENOTFOUND') {
    return `Host not found for ${url}. Check concurrencyChecker.backendUrl.`;
  }
  return `Request failed: ${e?.message ?? String(err)}${code ? ` (${code})` : ''}`;
}
