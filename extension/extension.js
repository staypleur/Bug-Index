'use strict';
const vscode = require('vscode');
const crypto = require('node:crypto');
const { excerpt, mask, safeUrl } = require('./collector');

function activate(context) {
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  status.command = 'bugIndex.connect';
  status.show(); context.subscriptions.push(status);
  let flushing = false;
  let connectionVersion = 0;
  const enabled = () => vscode.workspace.isTrusted && context.workspaceState.get('enabled', false);
  const update = () => { status.text = enabled() ? '$(bug) Bug Index: ON' : '$(bug) Bug Index: OFF'; status.tooltip = 'C · Python · Java 오류 도감'; };
  const notify = message => vscode.window.showWarningMessage(`Bug Index: ${message}`);
  async function pending() { try { return JSON.parse(await context.secrets.get('pending') || '[]'); } catch { return []; } }
  // Serialize queue mutations to avoid losing captures from simultaneous terminals.
  let queueChain = Promise.resolve();
  function mutateQueue(fn) { const operation = queueChain.then(async () => { const queue = await pending(); await context.secrets.store('pending', JSON.stringify(await fn(queue))); }); queueChain = operation.catch(() => {}); return operation; }
  async function flush() {
    if (flushing || !enabled()) return;
    const token = await context.secrets.get('token'), url = await context.secrets.get('url');
    if (!token || !url) return;
    flushing = true;
    const version = connectionVersion;
    try {
      await queueChain;
      for (const entry of await pending()) {
        if (!enabled() || version !== connectionVersion) break;
        const response = await fetch(`${url}/api/capture`, { method: 'POST', redirect: 'error', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(entry), signal: AbortSignal.timeout(15000) });
        if (!response.ok) { if ([401, 403].includes(response.status)) { await context.workspaceState.update('enabled', false); update(); notify('수집 토큰을 확인하고 다시 연결해주세요.'); } break; }
        const result = await response.json();
        await mutateQueue(queue => queue.filter(item => item.request_id !== entry.request_id));
        if (result.collected && !result.duplicate) vscode.window.showInformationMessage(`🐛 ${result.new_case ? '새로운 버그 발견!' : '버그 재등장!'} ${result.species} · +${result.xp_earned} XP`);
      }
    } catch { status.tooltip = '서버 연결을 기다리는 중입니다. 마스킹된 오류를 보관하고 재시도합니다.'; }
    finally { flushing = false; }
  }
  function command(name, handler) { context.subscriptions.push(vscode.commands.registerCommand(`bugIndex.${name}`, async () => { try { await handler(); } catch (error) { notify(error.message); } })); }
  command('connect', async () => {
    const oldUrl = await context.secrets.get('url');
    const value = await vscode.window.showInputBox({ title: 'Bug Index 서비스 주소', value: oldUrl || 'http://localhost:8000', prompt: '맥미니에서 운영하는 서비스의 HTTPS 주소' });
    if (!value) return;
    const url = safeUrl(value);
    const token = await vscode.window.showInputBox({ title: 'Bug Index 수집 토큰', password: true, prompt: '웹의 VS Code 연결 화면에서 발급한 토큰' });
    if (!token) return;
    const check = await fetch(`${url}/api/me`, { redirect: 'error', headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(15000) });
    if (!check.ok) throw new Error('서비스 주소와 토큰을 확인해주세요.');
    // Do not transfer a previous account's pending logs to a different connection.
    await context.workspaceState.update('enabled', false);
    connectionVersion++;
    await mutateQueue(() => []);
    await context.secrets.store('url', url); await context.secrets.store('token', token); update();
    vscode.window.showInformationMessage('Bug Index 연결 완료. Enable Collection 명령으로 현재 작업 공간의 수집을 켜주세요.');
  });
  command('enable', async () => {
    if (!vscode.workspace.isTrusted || !vscode.workspace.workspaceFolders?.length) throw new Error('신뢰한 프로젝트 폴더에서 수집을 켜주세요.');
    if (!await context.secrets.get('token')) return vscode.commands.executeCommand('bugIndex.connect');
    await context.workspaceState.update('enabled', true); update();
    vscode.window.showInformationMessage('현재 작업 공간의 오류 수집을 켰습니다. 터미널 셸 통합이 필요합니다.');
    await flush();
  });
  command('disable', async () => { await context.workspaceState.update('enabled', false); update(); });
  command('retry', flush);
  command('clear', async () => { await mutateQueue(() => []); vscode.window.showInformationMessage('보관 중인 오류를 삭제했습니다.'); });
  command('disconnect', async () => { connectionVersion++; await context.workspaceState.update('enabled', false); await mutateQueue(() => []); await context.secrets.delete('token'); await context.secrets.delete('url'); update(); });
  context.subscriptions.push(vscode.window.onDidStartTerminalShellExecution(async event => {
    if (!enabled()) return;
    const cwd = event.execution.cwd || vscode.workspace.workspaceFolders?.[0]?.uri;
    if (!cwd) return;
    const folder = vscode.workspace.getWorkspaceFolder(cwd);
    if (!folder) return;
    let output = '';
    try {
      // Start reading immediately; the stream closes once this execution finishes.
      for await (const chunk of event.execution.read()) output = (output + chunk).slice(-65536);
      if (!enabled()) return;
      const log = excerpt(output);
      if (!log) return;
      await mutateQueue(queue => { if (queue.length >= 50) { notify('대기 오류 50건이 찼습니다. 서버 연결 후 재시도해주세요.'); return queue; } return [...queue, { log, project: mask(folder.name).slice(0, 120), request_id: crypto.randomUUID() }]; });
      await flush();
    } catch { notify('터미널 오류를 읽지 못했습니다. 셸 통합 상태를 확인해주세요.'); }
  }));
  const timer = setInterval(() => flush().catch(() => {}), 30000);
  context.subscriptions.push({ dispose: () => clearInterval(timer) });
  update();
}
module.exports = { activate };
