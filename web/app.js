'use strict';
const $ = selector => document.querySelector(selector);
const state = { user: null, bugs: [], filter: 'all', view: 'dex' };
const el = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; };
let toastTimer;
function toast(message) { $('#toast').textContent = message; $('#toast').classList.remove('hidden'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.add('hidden'), 6000); }
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '입력 내용을 확인해주세요.');
  return data;
}
function date(timestamp) { return new Date(timestamp * 1000).toLocaleString('ko-KR'); }
async function refresh() {
  state.bugs = await api('/api/collection');
  const discovered = state.bugs.filter(b => b.discovered);
  $('#total').textContent = discovered.length;
  $('#encounters').textContent = state.bugs.reduce((a, b) => a + b.encounters, 0);
  $('#solved').textContent = state.bugs.reduce((a, b) => a + b.solved, 0);
  $('#mastered').textContent = state.bugs.filter(b => b.mastered).length;
  $('#collection-count').textContent = `${discovered.length} / ${state.bugs.length}`;
  $('#nav-count').textContent = discovered.length;
  $('#total-caption').textContent = discovered.length ? `${state.bugs.length}종 중 ${Math.round(discovered.length / state.bugs.length * 100)}% 발견` : '도감의 첫 페이지를 채워보세요';
  renderCards();
}
function renderCards() {
  const query = $('#search').value.trim().toLowerCase(), language = $('#language').value;
  let bugs = state.bugs.filter(b => (!language || b.language === language) && (!query || [b.name, b.category, b.language].join(' ').toLowerCase().includes(query)) &&
    (state.filter === 'all' || (state.filter === 'discovered' && b.discovered) || (state.filter === 'mastered' && b.mastered) || (state.filter === 'unknown' && !b.discovered)));
  const sort = $('#sort').value;
  bugs.sort((a, b) => sort === 'level' ? b.level - a.level || b.encounters - a.encounters : sort === 'name' ? a.name.localeCompare(b.name) : (b.last_seen || 0) - (a.last_seen || 0) || a.id - b.id);
  $('#cards').replaceChildren();
  $('#empty-search').classList.toggle('hidden', !!bugs.length);
  for (const bug of bugs) {
    const card = el(bug.discovered ? 'button' : 'div', `bug-card ${bug.discovered ? '' : 'unknown'}`);
    const top = el('div', 'card-top'); top.append(el('span', '', `NO. ${String(bug.id).padStart(3, '0')}`), el('span', `rarity ${bug.rarity}`, bug.rarity.toUpperCase()));
    card.append(top, el('div', 'creature', bug.discovered ? bug.icon : '?'), el('h3', '', bug.discovered ? bug.name : '??????????'));
    const meta = el('div', 'bug-meta'); meta.append(el('b', '', bug.language), el('span', '', '·'), document.createTextNode(bug.discovered ? bug.category : '아직 만나지 않은 버그'));
    card.append(meta);
    const bottom = el('div', 'card-bottom'); bottom.append(el('span', 'level', bug.discovered ? `Lv. ${bug.level}` : 'UNDISCOVERED'), el('span', '', bug.discovered ? `조우 ${bug.encounters}회 · 해결 ${bug.solved}건` : '다음 만남을 기다리고 있어요'));
    card.append(bottom);
    if (bug.discovered) { const xp = el('div', 'xp'); const fill = el('i'); fill.style.width = `${bug.progress * 100}%`; xp.append(fill); card.append(xp); card.setAttribute('aria-label', `${bug.name}, 레벨 ${bug.level}, 조우 ${bug.encounters}회`); card.addEventListener('click', () => showDetail(bug).catch(e => toast(e.message))); }
    if (bug.mastered) card.append(el('span', 'master-tag', '✧ MASTER'));
    $('#cards').append(card);
  }
}
async function showDetail(bug) {
  const cases = await api(`/api/species/${bug.id}/cases`);
  $('#detail-number').textContent = `BUG INDEX / NO. ${String(bug.id).padStart(3, '0')}`;
  $('#detail-title').textContent = `${bug.icon} ${bug.name}`;
  $('#detail-summary').textContent = `Lv. ${bug.level} · ${bug.xp}/${bug.next_level_xp} XP · 조우 ${bug.encounters}회 · 해결 ${bug.solved}건 · ${bug.mastered ? 'MASTER' : '마스터 조건: 조우 5회 + 서로 다른 버그 3건 해결'}`;
  $('#detail-cases').replaceChildren();
  for (const item of cases) {
    const form = el('form', 'case');
    form.append(el('h3', '', item.project), el('p', 'case-meta', `조우 ${item.encounters}회 · 최초 ${date(item.first_seen)}`));
    const details = el('details'); details.append(el('summary', '', '최근 발생 로그와 식별 정보 보기'));
    details.append(el('p', 'muted', `Fingerprint: ${item.fingerprint}`));
    for (const occurrence of item.occurrences) details.append(el('p', 'case-meta', date(occurrence.occurred_at)), el('pre', '', occurrence.log));
    form.append(details);
    for (const [key, label, rows] of [['cause', '발생 원인', 2], ['solution', '해결 방법', 3], ['memo', '내가 배운 것', 2]]) { const field = el('label', '', label); const input = el('textarea'); input.name = key; input.rows = rows; input.maxLength = key === 'solution' ? 8000 : 4000; input.value = item[key]; field.append(input); form.append(field); }
    const check = el('label', 'check'); const checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.name = 'solved'; checkbox.checked = item.solved_at !== null; check.append(checkbox, document.createTextNode('해결 완료 · 원인과 해결 방법을 기록했어요')); form.append(check);
    const submit = el('button', 'primary', '기록 저장하기'); submit.type = 'submit'; form.append(submit);
    form.addEventListener('submit', async event => { event.preventDefault(); submit.disabled = true; try { const data = new FormData(form); await api(`/api/cases/${item.id}`, { method: 'PATCH', body: JSON.stringify({ cause: data.get('cause'), solution: data.get('solution'), memo: data.get('memo'), solved: checkbox.checked }) }); await refresh(); toast('해결 기록을 저장했습니다.'); await showDetail(state.bugs.find(b => b.id === bug.id)); } catch (e) { toast(e.message); } finally { submit.disabled = false; } });
    $('#detail-cases').append(form);
  }
  if (!$('#detail-dialog').open) $('#detail-dialog').showModal();
}
function lockPanel(target, title) {
  const panel = el('div', 'panel pro-lock'); panel.append(el('div', 'lock', '✧'), el('span', 'tag', 'BUG INDEX PRO'), el('h2', '', title), el('p', '', '고급 통계와 랭킹 조회는 Pro 기능입니다.'), el('p', '', '월 구독은 준비 중입니다. 가격과 결제 일정은 추후 안내합니다.'));
  target.replaceChildren(panel);
}
function bars(title, rows) {
  const panel = el('div', 'panel'); panel.append(el('h2', '', title));
  if (!rows.length || rows.every(r => !r.count)) { panel.append(el('p', '', '아직 기록이 없습니다. 첫 오류를 수집해보세요.')); return panel; }
  const max = Math.max(...rows.map(r => r.count), 1);
  for (const row of rows) { const line = el('div', 'bar-row'); const bar = el('div', 'bar'); const fill = el('i'); fill.style.width = `${row.count / max * 100}%`; bar.append(fill); line.append(el('span', '', row.label), bar, el('span', '', row.count)); panel.append(line); }
  return panel;
}
async function showView(view) {
  state.view = view;
  for (const section of document.querySelectorAll('.view')) section.classList.toggle('hidden', section.id !== `${view}-view`);
  for (const nav of document.querySelectorAll('.nav')) nav.classList.toggle('active', nav.dataset.view === view);
  $('#breadcrumb').textContent = { dex: '버그 도감', stats: '고급 통계', ranking: '헌터 랭킹', connect: 'VS Code 연결' }[view];
  if (view !== 'connect') { $('#new-token').value = ''; $('#token-result').classList.add('hidden'); }
  if (view === 'stats') {
    if (!state.user.pro) return lockPanel($('#stats-content'), '내 오류 패턴을 더 깊게 살펴보세요.');
    const stats = await api('/api/stats');
    $('#stats-content').replaceChildren(bars('언어별 조우', Object.entries(stats.languages).map(([label, count]) => ({ label, count }))), bars('가장 많이 만난 오류', stats.top_errors.map(b => ({ label: b.name, count: b.encounters }))), bars('프로젝트별 조우', stats.projects.map(p => ({ label: p.project, count: p.encounters }))), bars('최근 30일의 수집 기록 · UTC 기준', stats.days.map(d => ({ label: d.day, count: d.count }))));
  }
  if (view === 'ranking') {
    if (!state.user.pro) return lockPanel($('#ranking-content'), '함께 성장하는 버그 헌터들을 만나보세요.');
    const ranks = await api('/api/ranking'); const panel = el('div', 'panel');
    panel.append(el('p', '', '랭킹 공개에 동의한 사용자만 표시됩니다. 발생 횟수는 점수에 포함하지 않습니다.'));
    if (!ranks.length) panel.append(el('p', '', '아직 공개된 랭킹이 없습니다. VS Code 연결 화면에서 랭킹 공개를 설정할 수 있습니다.'));
    const table = el('table'), head = el('tr'); for (const label of ['순위', '헌터', '해결', '마스터', '점수']) head.append(el('th', '', label)); const thead = el('thead'); thead.append(head); table.append(thead); const tbody = el('tbody');
    for (const rank of ranks) { const row = el('tr'); for (const value of [rank.rank, rank.login, rank.solved, rank.mastered, rank.score]) row.append(el('td', '', value)); tbody.append(row); } table.append(tbody); panel.append(table); $('#ranking-content').replaceChildren(panel);
  }
  if (view === 'connect') await loadTokens();
}
async function loadTokens() {
  const tokens = await api('/api/tokens'); $('#token-list').replaceChildren();
  if (!tokens.length) $('#token-list').append(el('p', 'muted', '활성 토큰이 없습니다.'));
  for (const token of tokens) { const row = el('div', 'token-row'); row.append(el('span', '', `${token.label} · ${date(token.created)}`)); const revoke = el('button', 'quiet', '폐기'); revoke.addEventListener('click', async () => { try { await api(`/api/tokens/${token.digest}`, { method: 'DELETE', body: '{}' }); await loadTokens(); toast('토큰을 폐기했습니다.'); } catch (e) { toast(e.message); } }); row.append(revoke); $('#token-list').append(row); }
}
for (const nav of document.querySelectorAll('.nav')) nav.addEventListener('click', () => { if (state.user) showView(nav.dataset.view).catch(e => toast(e.message)); });
for (const button of document.querySelectorAll('[data-filter]')) button.addEventListener('click', () => { state.filter = button.dataset.filter; for (const tab of document.querySelectorAll('[data-filter]')) tab.classList.toggle('selected', tab === button); renderCards(); });
for (const selector of ['#search', '#language', '#sort']) $(selector).addEventListener(selector === '#search' ? 'input' : 'change', renderCards);
for (const button of document.querySelectorAll('[data-close]')) button.addEventListener('click', () => document.getElementById(button.dataset.close).close());
document.addEventListener('keydown', event => { if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && state.view === 'dex' && state.user && !document.querySelector('dialog[open]')) { event.preventDefault(); $('#search').focus(); } });
$('#capture-open').addEventListener('click', () => $('#capture-dialog').showModal());
$('#tip-connect').addEventListener('click', () => showView('connect').catch(e => toast(e.message)));
$('#capture-form').addEventListener('submit', async event => { event.preventDefault(); const form = event.target; const button = form.querySelector('[type=submit]'); button.disabled = true; try { const data = new FormData(form); const result = await api('/api/capture', { method: 'POST', body: JSON.stringify({ project: data.get('project'), language: data.get('language') || null, log: data.get('log'), request_id: crypto.randomUUID() }) }); if (!result.collected) return toast(result.reason); $('#capture-dialog').close(); form.reset(); await refresh(); toast(`${result.new_case ? '새로운 버그 발견!' : '다시 만났네요!'} ${result.species} · +${result.xp_earned} XP`); } catch (e) { toast(e.message); } finally { button.disabled = false; } });
$('#create-token').addEventListener('click', async () => { const button = $('#create-token'); button.disabled = true; try { const result = await api('/api/tokens', { method: 'POST', body: JSON.stringify({ label: 'VS Code' }) }); $('#new-token').value = result.token; $('#token-result').classList.remove('hidden'); await loadTokens(); } catch (e) { toast(e.message); } finally { button.disabled = false; } });
$('#copy-token').addEventListener('click', async () => { try { await navigator.clipboard.writeText($('#new-token').value); toast('토큰을 복사했습니다.'); } catch { $('#new-token').select(); toast('토큰을 선택했습니다. 직접 복사해주세요.'); } });
$('#ranking-opt-in').addEventListener('change', async event => { const previous = state.user.ranking_opt_in; try { await api('/api/preferences', { method: 'PATCH', body: JSON.stringify({ ranking_opt_in: event.target.checked }) }); state.user.ranking_opt_in = event.target.checked; toast('랭킹 공개 설정을 저장했습니다.'); } catch (e) { event.target.checked = previous; toast(e.message); } });
$('#logout').addEventListener('click', async () => { try { await api('/api/logout', { method: 'POST', body: '{}' }); location.reload(); } catch (e) { toast(e.message); } });
async function start() {
  const config = await api('/api/config');
  try { state.user = await api('/api/me'); } catch { $('#login-screen').classList.remove('hidden'); $('#dev-login').classList.toggle('hidden', !config.dev_login); if (!config.github_configured) { $('#github-login').classList.add('hidden'); $('#login-note').textContent = 'GitHub 로그인 설정을 준비 중입니다.'; } return; }
  $('#username').textContent = state.user.login;
  $('#plan-label').textContent = state.user.pro ? 'PRO PLAN · 고급 통계 & 랭킹' : 'FREE PLAN · 기본 도감';
  $('#logout').classList.remove('hidden'); $('#ranking-opt-in').checked = state.user.ranking_opt_in;
  await refresh(); await showView('dex');
}
start().catch(e => toast(`서비스 연결을 확인해주세요. ${e.message}`));
setInterval(() => {
  if (state.user && state.view === 'dex' && !document.hidden && !document.querySelector('dialog[open]')) refresh().catch(() => {});
}, 20000);
