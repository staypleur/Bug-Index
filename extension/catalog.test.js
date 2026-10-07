const { test } = require('node:test');
const assert = require('node:assert/strict');
const entries = require('./errors.json');
const { excerpt } = require('./collector');

test('every supported diagnostic reaches the API through the collector', () => {
  for (const entry of entries) assert.ok(excerpt(entry.sample), `${entry.language} ${entry.name} is missed`);
});
test('plain documentation, source text and warnings are ignored', () => {
  for (const output of ['The documentation mentions NullPointerException.', '    raise TypeError("bad")', 'main.c:2: warning: implicit declaration of function run', 'KeyboardInterrupt', 'SystemExit: 0']) assert.equal(excerpt(output), null);
});
test('compile errors keep their source location', () => {
  assert.match(excerpt("main.c:2:1: error: expected ';' before 'return'"), /main\.c:2:1: error/);
  assert.match(excerpt('Main.java:2: error: cannot find symbol'), /Main\.java:2: error/);
});
