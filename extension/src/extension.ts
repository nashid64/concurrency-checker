import * as vscode from 'vscode';
import { AnalyzeResult, diagnosticText, explainNetworkError, normalizeResponse } from './analysis';

let diagnostics: vscode.DiagnosticCollection;
let statusItem: vscode.StatusBarItem;
let output: vscode.OutputChannel;
const inflight = new Map<string, AbortController>();

function cfg() {
  const c = vscode.workspace.getConfiguration('concurrencyChecker');
  return {
    url: String(c.get('backendUrl', 'http://127.0.0.1:8000')).replace(/\/+$/, ''),
    apiKey: String(c.get('apiKey', '')),
    mode: String(c.get('detectorMode', 'server-default')),
    onSave: Boolean(c.get('analyzeOnSave', true)),
    timeout: Number(c.get('timeoutSeconds', 90)),
    maxChars: Number(c.get('maxFileChars', 60000)),
  };
}

function headers(apiKey: string): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiKey) {
    h['X-API-Key'] = apiKey;
  }
  return h;
}

function setStatus(text: string, tooltip?: string) {
  statusItem.text = text;
  statusItem.tooltip = tooltip ?? 'Click to analyze the current Java file for concurrency bugs';
  statusItem.show();
}

function log(msg: string) {
  output.appendLine(`[${new Date().toLocaleTimeString()}] ${msg}`);
}

async function analyze(doc: vscode.TextDocument, userInitiated: boolean): Promise<void> {
  if (doc.languageId !== 'java') {
    if (userInitiated) {
      vscode.window.showInformationMessage('Concurrency Checker works on Java files only.');
    }
    return;
  }
  const c = cfg();
  const code = doc.getText();
  if (code.length > c.maxChars) {
    const msg = `File is too large (${code.length} chars, limit ${c.maxChars}). Raise concurrencyChecker.maxFileChars if the backend allows it.`;
    log(msg);
    if (userInitiated) {
      vscode.window.showWarningMessage(msg);
    }
    return;
  }
  if (!code.trim()) {
    diagnostics.delete(doc.uri);
    return;
  }

  const key = doc.uri.toString();
  inflight.get(key)?.abort();
  const controller = new AbortController();
  inflight.set(key, controller);
  const timer = setTimeout(() => controller.abort(), c.timeout * 1000);
  const versionAtStart = doc.version;

  setStatus('$(sync~spin) Analyzing…');
  log(`Analyzing ${doc.fileName} (${code.length} chars) via ${c.url}`);
  try {
    const body: Record<string, unknown> = {
      code,
      language: 'java',
      filename: doc.fileName.split(/[\\/]/).pop(),
    };
    if (c.mode !== 'server-default') {
      body.mode = c.mode;
    }
    const res = await fetch(`${c.url}/analyze`, {
      method: 'POST',
      headers: headers(c.apiKey),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = (await res.json()) as { detail?: unknown };
        detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j);
      } catch {
        /* ignore body parse errors */
      }
      throw new Error(`Backend returned ${res.status}: ${detail}`);
    }
    const result = normalizeResponse(await res.json(), doc.lineCount);
    if (doc.isClosed || doc.version !== versionAtStart) {
      log('File changed while analyzing - result discarded. Save again to re-run.');
      setStatus('$(history) Outdated result');
      return;
    }
    show(doc, result);
  } catch (err) {
    if (controller.signal.aborted && inflight.get(key) !== controller) {
      return; // replaced by a newer request
    }
    const message =
      err instanceof Error && err.message.startsWith('Backend returned')
        ? err.message
        : explainNetworkError(err, c.url);
    log(`ERROR: ${message}`);
    setStatus('$(error) Concurrency Checker error', message);
    if (userInitiated) {
      vscode.window.showErrorMessage(`Concurrency Checker: ${message}`);
    }
  } finally {
    clearTimeout(timer);
    if (inflight.get(key) === controller) {
      inflight.delete(key);
    }
  }
}

function show(doc: vscode.TextDocument, result: AnalyzeResult) {
  const list: vscode.Diagnostic[] = result.bugs.map((b) => {
    const startLine = Math.min(b.line - 1, doc.lineCount - 1);
    const endLine = Math.min(b.endLine - 1, doc.lineCount - 1);
    const first = doc.lineAt(startLine);
    const last = doc.lineAt(endLine);
    const range = new vscode.Range(startLine, first.firstNonWhitespaceCharacterIndex, endLine, last.text.length);
    const sev =
      b.severity === 'error'
        ? vscode.DiagnosticSeverity.Error
        : b.severity === 'info'
          ? vscode.DiagnosticSeverity.Information
          : vscode.DiagnosticSeverity.Warning;
    const d = new vscode.Diagnostic(range, diagnosticText(b), sev);
    d.source = 'Concurrency Checker';
    d.code = b.type;
    return d;
  });
  diagnostics.set(doc.uri, list);
  log(`Result: verdict=${result.verdict}, ${list.length} issue(s), detector=${result.detector}${result.note ? ` (${result.note})` : ''}`);
  if (list.length === 0) {
    setStatus('$(check) No concurrency issues', `Detector: ${result.detector}${result.note ? ' - ' + result.note : ''}`);
  } else {
    setStatus(`$(warning) ${list.length} concurrency issue${list.length > 1 ? 's' : ''}`, `Detector: ${result.detector}. Click to re-analyze.`);
  }
}

async function checkBackend() {
  const c = cfg();
  try {
    const res = await fetch(`${c.url}/health`, { headers: headers(c.apiKey), signal: AbortSignal.timeout(10000) });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const h = (await res.json()) as Record<string, unknown>;
    log(`Health: ${JSON.stringify(h)}`);
    vscode.window.showInformationMessage(
      `Backend OK. Default mode: ${h.default_mode}. LLM key set: ${h.llm_configured}. Local model found: ${h.model_available}.`
    );
  } catch (err) {
    const message = explainNetworkError(err, c.url);
    log(`ERROR: ${message}`);
    vscode.window.showErrorMessage(`Concurrency Checker: ${message}`);
  }
}

export function activate(context: vscode.ExtensionContext) {
  diagnostics = vscode.languages.createDiagnosticCollection('concurrency-checker');
  output = vscode.window.createOutputChannel('Concurrency Checker');
  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusItem.command = 'concurrencyChecker.analyzeFile';
  setStatus('$(bug) Concurrency Checker');

  context.subscriptions.push(
    diagnostics,
    output,
    statusItem,
    vscode.commands.registerCommand('concurrencyChecker.analyzeFile', () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showInformationMessage('Open a Java file first.');
        return;
      }
      return analyze(editor.document, true);
    }),
    vscode.commands.registerCommand('concurrencyChecker.clear', () => {
      diagnostics.clear();
      setStatus('$(bug) Concurrency Checker');
    }),
    vscode.commands.registerCommand('concurrencyChecker.checkBackend', checkBackend),
    vscode.commands.registerCommand('concurrencyChecker.showOutput', () => output.show(true)),
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (cfg().onSave && doc.languageId === 'java') {
        void analyze(doc, false);
      }
    }),
    vscode.workspace.onDidChangeTextDocument((e) => {
      // old markers would point at wrong lines after an edit, so remove them
      if (e.contentChanges.length > 0 && diagnostics.has(e.document.uri)) {
        diagnostics.delete(e.document.uri);
      }
    }),
    vscode.workspace.onDidCloseTextDocument((doc) => {
      diagnostics.delete(doc.uri);
      inflight.get(doc.uri.toString())?.abort();
      inflight.delete(doc.uri.toString());
    })
  );
  log('Concurrency Checker activated');
}

export function deactivate() {
  for (const c of inflight.values()) {
    c.abort();
  }
  inflight.clear();
}
