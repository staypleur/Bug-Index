'use strict';
// Library diagnostics are also covered by the shared traceback detector. Avoid
// running thousands of library regexes just to decide whether to send a log.
const RULES = require('./errors.json').filter(entry => !entry.context).map(entry => new RegExp(entry.pattern, 'im'));
const DETECTORS = require('./diagnostics.json').map(entry => ({ rule: new RegExp(entry.pattern, 'm'), context: entry.context ? new RegExp(entry.context, 'm') : null }));
const PREFIXES = require('./diagnostic-prefixes.json').map(pattern => new RegExp(pattern, 'gm'));
function mask(text) {
  return text.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '')
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [REDACTED]')
    .replace(/(\b(?:api[_-]?key|password|passwd|secret|token|authorization|client_secret)\b["']?\s*[:=]\s*)(?:["'][^"'\n]*["']|[^\s,;]+)/gi, '$1[REDACTED]')
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [REDACTED]')
    .replace(/\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})\b/g, '[REDACTED]')
    .replace(/(https?:\/\/|postgres(?:ql)?:\/\/|mysql:\/\/)([^\s/@]+)@/g, '$1[REDACTED]@')
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[EMAIL]')
    .replace(/(?:[A-Z]:[\\/]Users[\\/]|\/Users\/|\/home\/)[^/\\\s"']+/gi, '~/');
}
function excerpt(output) {
  let clean = mask(output.replace(/\r\n/g, '\n'));
  for (const prefix of PREFIXES) clean = clean.replace(prefix, '');
  const matches = RULES.map(rule => clean.match(rule)).filter(Boolean);
  for (const detector of DETECTORS) if (!detector.context || detector.context.test(clean)) {
    const match = clean.match(detector.rule);
    if (match) matches.push(match);
  }
  const match = matches.sort((a, b) => a.index - b.index)[0];
  if (!match) return null;
  const before = clean.slice(0, match.index), traceback = before.lastIndexOf('Traceback (most recent call last):');
  const start = traceback >= 0 ? traceback : Math.max(0, before.lastIndexOf('\n', Math.max(0, before.length - 2)) + 1);
  const lines = clean.slice(start).split('\n');
  // Only send bounded error context, never the entire terminal session.
  return lines.slice(0, 80).join('\n').slice(-32768);
}
function safeUrl(value) {
  const url = new URL(value);
  if (url.username || url.password || url.search || url.hash || !['https:', 'http:'].includes(url.protocol)) throw new Error('HTTPS 서비스 URL을 입력해주세요.');
  if (url.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) throw new Error('외부 서버 연결에는 HTTPS가 필요합니다.');
  return url.origin;
}
module.exports = { mask, excerpt, safeUrl };
