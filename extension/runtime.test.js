'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');

function setup() {
  const commands = new Map(), secrets = new Map([['token', 'test-token'], ['url', 'http://localhost:8000']]), state = new Map(), disposables = [];
  let terminalListener;
  const uri = { path: '/workspace', scheme: 'file' };
  const vscode = {
    StatusBarAlignment: { Right: 1 },
    workspace: { isTrusted: true, workspaceFolders: [{ uri }], getWorkspaceFolder: () => ({ name: 'test-project', uri }) },
    commands: { registerCommand: (name, fn) => { commands.set(name, fn); return { dispose() {} }; }, executeCommand: async name => commands.get(name)?.() },
    window: {
      createStatusBarItem: () => ({ show() {}, dispose() {} }),
      showWarningMessage() {}, showInformationMessage() {},
      onDidStartTerminalShellExecution: fn => { terminalListener = fn; return { dispose() {} }; }
    }
  };
  const context = {
    subscriptions: disposables,
    secrets: { get: async key => secrets.get(key), store: async (key, value) => secrets.set(key, value), delete: async key => secrets.delete(key) },
    workspaceState: { get: (key, fallback) => state.has(key) ? state.get(key) : fallback, update: async (key, value) => state.set(key, value) }
  };
  const original = Module._load;
  Module._load = function(name, ...args) { if (name === 'vscode') return vscode; return original.call(this, name, ...args); };
  try { delete require.cache[require.resolve('./extension')]; require('./extension').activate(context); } finally { Module._load = original; }
  return {
    run: name => commands.get(`bugIndex.${name}`)(),
    emit: text => terminalListener({ execution: { cwd: uri, async *read() { yield text; } } }),
    queue: () => JSON.parse(secrets.get('pending') || '[]'),
    dispose: () => disposables.forEach(d => d.dispose()),
  };
}

test('collection is disabled until enabled for the workspace', async () => {
  const runtime = setup(); try { await runtime.emit('TypeError: example'); assert.equal(runtime.queue().length, 0); } finally { runtime.dispose(); }
});

test('automatic capture masks data before sending', async () => {
  const runtime = setup(), original = global.fetch; const requests = [];
  global.fetch = async (url, options) => { requests.push(JSON.parse(options.body)); return { ok: true, json: async () => ({ collected: true, species: 'TypeError', xp_earned: 1 }) }; };
  try { await runtime.run('enable'); await runtime.emit('Traceback (most recent call last):\n File "/Users/alice/main.py", line 2, in run\nTypeError: PASSWORD=verysecret'); assert.equal(requests.length, 1); assert.ok(!requests[0].log.includes('verysecret')); assert.ok(!requests[0].log.includes('alice')); assert.equal(runtime.queue().length, 0); } finally { global.fetch = original; runtime.dispose(); }
});

test('offline captures retain the same id on retry', async () => {
  const runtime = setup(), original = global.fetch; const requests = [];
  global.fetch = async () => { throw new Error('offline'); };
  try { await runtime.run('enable'); await runtime.emit('Segmentation fault'); assert.equal(runtime.queue().length, 1); const id = runtime.queue()[0].request_id; global.fetch = async (url, options) => { requests.push(JSON.parse(options.body)); return { ok: true, json: async () => ({ collected: true, duplicate: true }) }; }; await runtime.run('retry'); assert.equal(requests[0].request_id, id); assert.equal(runtime.queue().length, 0); } finally { global.fetch = original; runtime.dispose(); }
});

test('normal output ignored and disconnect clears pending data', async () => {
  const runtime = setup(), original = global.fetch;
  global.fetch = async () => { throw new Error('offline'); };
  try { await runtime.run('enable'); await runtime.emit('all good'); assert.equal(runtime.queue().length, 0); await runtime.emit('java.lang.NullPointerException'); assert.equal(runtime.queue().length, 1); await runtime.run('disconnect'); assert.equal(runtime.queue().length, 0); await runtime.emit('TypeError: ignored'); assert.equal(runtime.queue().length, 0); } finally { global.fetch = original; runtime.dispose(); }
});
