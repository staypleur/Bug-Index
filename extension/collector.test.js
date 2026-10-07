const { test } = require('node:test');
const assert = require('node:assert/strict');
const { mask, excerpt, safeUrl, languageHint } = require('./collector');
test('C command hints support quoted Windows tools and reject C++ or echo', () => {
  assert.equal(languageHint('gcc main.c -o app'), 'C');
  assert.equal(languageHint('& "C:\\Program Files\\LLVM\\bin\\clang.exe" "my app.c"'), 'C');
  assert.equal(languageHint('cl.exe /TC main.c'), 'C');
  assert.equal(languageHint('cppcheck --language=c src'), 'C');
  assert.equal(languageHint('gcc main.c other.cpp'), undefined);
  assert.equal(languageHint('echo gcc main.c'), undefined);
  assert.equal(languageHint('javac Main.java'), undefined);
});
test('C-only linker output needs a C command or source context', () => {
  assert.equal(excerpt('ld.lld: error: cannot open input file missing.o'), null);
  assert.match(excerpt('ld.lld: error: cannot open input file missing.o', 'C'), /ld.lld/);
  assert.match(excerpt('main.c\nmain.obj : error LNK2019: unresolved external symbol absent'), /LNK2019/);
  assert.match(excerpt('main.c(2): error C2065: absent: undeclared identifier'), /C2065/);
  assert.equal(excerpt('main.cpp(2): error C2065: absent: undeclared identifier'), null);
  assert.equal(excerpt('main.c(2): warning C4100: unused parameter'), null);
});
test('Android Logcat prefixes are normalized before collection', () => {
  for (const prefix of ['10-07 12:34:56.123 123 456 E AndroidRuntime: ', 'E/AndroidRuntime( 123): ']) {
    const log = excerpt(prefix + 'java.lang.IllegalStateException: rejected state\n' + prefix + '    at android.app.Activity.run(Activity.java:12)');
    assert.match(log, /IllegalStateException/);
    assert.match(log, /at android.app.Activity/);
    assert.ok(!log.includes('AndroidRuntime:'));
  }
});
test('normal output does not create a bug', () => assert.equal(excerpt('Hello world\nexit code 0'), null));
test('Python trace keeps source frames and hides secrets', () => {
  const log = excerpt('regular console output\nTraceback (most recent call last):\n  File "/Users/alice/app/main.py", line 2, in run\nTypeError: API_KEY=supersecret\n');
  assert.match(log, /Traceback/); assert.match(log, /main.py/); assert.ok(!log.includes('alice')); assert.ok(!log.includes('supersecret')); assert.ok(!log.includes('regular console'));
});
test('Java and C errors are collected', () => { assert.match(excerpt('java.lang.NullPointerException\n at Main.main(Main.java:2)'), /NullPointer/); assert.match(excerpt('Segmentation fault (core dumped)'), /Segmentation/); });
test('structured secrets and credential URLs are masked', () => { const clean = mask('"password": "abc xyz" postgres://user:pass@db/x Authorization: Bearer abc123 github_pat_abc123 alice@example.com'); assert.ok(!clean.includes('abc xyz')); assert.ok(!clean.includes('user:pass')); assert.ok(!clean.includes('abc123')); assert.ok(!clean.includes('alice@')); });
test('external URLs require HTTPS and credentials are rejected', () => { assert.equal(safeUrl('https://bugs.example.com/path'), 'https://bugs.example.com'); assert.equal(safeUrl('http://localhost:8000'), 'http://localhost:8000'); assert.throws(() => safeUrl('http://server.local')); assert.throws(() => safeUrl('https://user:pass@example.com')); });
