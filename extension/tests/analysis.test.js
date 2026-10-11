const test = require('node:test');
const assert = require('node:assert');
const { normalizeResponse, diagnosticText, explainNetworkError } = require('../out/analysis.js');

test('normalizes a normal backend response', () => {
  const r = normalizeResponse(
    { bugs: [{ type: 'deadlock', line: 5, message: 'lock order', suggestion: 'fix order' }], verdict: 'deadlock', detector: 'llm', elapsed_ms: 12 },
    20
  );
  assert.strictEqual(r.bugs.length, 1);
  assert.strictEqual(r.bugs[0].severity, 'error');
  assert.strictEqual(r.bugs[0].endLine, 5);
  assert.strictEqual(r.elapsedMs, 12);
});

test('clamps lines and survives garbage', () => {
  const r = normalizeResponse({ bugs: [{ type: 'race_condition', line: 999, end_line: 2 }, null, 'x', { line: 'abc' }] }, 10);
  assert.strictEqual(r.bugs.length, 2);
  assert.strictEqual(r.bugs[0].line, 10);
  assert.strictEqual(r.bugs[0].endLine, 10);
  assert.strictEqual(r.bugs[1].line, 1);
  assert.strictEqual(normalizeResponse(null, 5).bugs.length, 0);
  assert.strictEqual(normalizeResponse(undefined, 5).verdict, 'safe');
});

test('diagnostic text and network errors', () => {
  assert.match(diagnosticText({ type: 'race_condition', line: 1, endLine: 1, severity: 'warning', message: 'm', suggestion: 's' }), /race condition.*\nFix: s/);
  assert.match(explainNetworkError({ cause: { code: 'ECONNREFUSED' } }, 'http://x'), /Is the backend running/);
  assert.match(explainNetworkError({ name: 'AbortError' }, 'http://x'), /timeout/);
});
