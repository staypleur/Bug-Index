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

test('unknown exceptions with actual traceback evidence reach the API', () => {
  assert.match(excerpt('Traceback (most recent call last):\n  File "main.py", line 2, in run\nCustomProjectError: rejected request'), /CustomProjectError/);
  assert.match(excerpt('Exception in thread "main" com.example.CustomFailureException: rejected\n  at com.example.Main.run(Main.java:2)'), /CustomFailureException/);
  assert.equal(excerpt('The docs mention CustomProjectError: sample text'), null);
});

test('catalog has 5000+ real source-backed entries', () => {
  assert.ok(entries.length >= 5000);
  for (const entry of entries.filter(e => e.verification === 'source-template')) {
    assert.match(entry.source, /^https:\/\/github.com\/[^/]+\/[^/]+\/blob\/[a-f0-9]{40}\/.+#L\d+$/);
    assert.ok(entry.context && entry.package);
  }
});
