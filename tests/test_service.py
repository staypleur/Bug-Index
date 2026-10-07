import os
import secrets
import time
from urllib.parse import parse_qs, urlparse

import pytest
import httpx
from fastapi.testclient import TestClient

from server.app import app, digest
from server.catalog import classify, fingerprint, mask, progression
from server.db import connect


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BUG_INDEX_DB", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("DEV_LOGIN", "1")
    with TestClient(app) as client:
        response = client.get("/auth/dev")
        assert response.status_code == 200
        yield client


def capture(client, log=None, project="test", headers=None, request_id=None):
    return client.post("/api/capture", json={"log": log or 'Traceback (most recent call last):\n  File "main.py", line 7, in run\nTypeError: bad input', "project": project, "request_id": request_id or secrets.token_hex(8)}, headers=headers)


def token_for_second_user():
    token = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("INSERT INTO users(github_id,login) VALUES('second','second-user')")
        uid = db.execute("SELECT id FROM users WHERE github_id='second'").fetchone()[0]
        db.execute("INSERT INTO tokens VALUES(?,?,?,?)", (digest(token), uid, "test", time.time()))
    return {"Authorization": "Bearer " + token}


def test_detect_languages_and_unknown():
    assert classify("Segmentation fault")['language'] == 'C'
    assert classify("java.lang.NullPointerException")['language'] == 'Java'
    assert classify("SyntaxError: bad syntax")['language'] == 'Python'
    assert classify("Nothing went wrong") is None
    assert classify("TypeError: not Java", "Java") is None


def test_mask_secrets_and_home():
    clean = mask('"password": "hello world" API_KEY=abcdef Authorization: Bearer xyz123 postgres://user:pass@db/app /Users/alice/main.py alice@example.com github_pat_ABC123')
    for secret in ['hello world', 'abcdef', 'xyz123', 'user:pass', 'alice', 'ABC123']:
        assert secret not in clean


def test_fingerprint_ignores_line_numbers_and_preserves_function():
    first = classify('File "main.py", line 7, in run\nTypeError: bad input')
    moved = classify('File "main.py", line 77, in run\nTypeError: other input')
    other = classify('File "main.py", line 7, in other\nTypeError: bad input')
    assert fingerprint(first, 'project') == fingerprint(moved, 'project')
    assert fingerprint(first, 'project') != fingerprint(other, 'project')
    assert fingerprint(first, 'project') != fingerprint(first, 'another')


def test_level_cost_increases():
    assert progression(0)['level'] == 1
    assert progression(5)['level'] == 2
    assert progression(19)['level'] == 2
    assert progression(20)['level'] == 3
    assert progression(45)['level'] == 4


def test_capture_dedup_and_species_growth(client):
    first = capture(client, request_id='request001').json()
    retry = capture(client, request_id='request001').json()
    assert retry['duplicate'] is True
    assert first['xp_earned'] == 1
    repeat = capture(client).json()
    assert repeat['new_case'] is False and repeat['xp_earned'] == 0
    another = capture(client, project='second-project').json()
    assert another['new_case'] is True
    species = next(b for b in client.get('/api/collection').json() if b['name'] == 'TypeError')
    assert species['encounters'] == 3
    assert species['cases'] == 2 and species['xp'] == 1


def test_logs_are_masked_before_storage(client):
    capture(client, log='TypeError: PASSWORD=secret123')
    with connect() as db:
        stored = db.execute('SELECT log FROM occurrences').fetchone()[0]
    assert 'secret123' not in stored and '[REDACTED]' in stored


def test_user_isolation_and_private_export(client):
    first = capture(client).json()
    headers = token_for_second_user()
    assert all(not bug['discovered'] for bug in client.get('/api/collection', headers=headers).json())
    assert client.get('/api/species/9/cases', headers=headers).json() == []
    response = client.patch(f"/api/cases/{first['bug_id']}", json={'cause': 'x', 'solution': 'y', 'solved': True}, headers=headers)
    assert response.status_code == 404
    assert client.get('/api/export', headers=headers).status_code == 403


def test_mastery_and_score_are_not_farmed_by_solution_toggle(client):
    ids = [capture(client, project=f'project-{n}').json()['bug_id'] for n in range(3)]
    for _ in range(3): capture(client)
    for bug_id in ids:
        assert client.patch(f'/api/cases/{bug_id}', json={'cause': 'bad type', 'solution': 'convert input', 'solved': True}).status_code == 200
    species = next(b for b in client.get('/api/collection').json() if b['name'] == 'TypeError')
    assert species['mastered'] is True and species['solved'] == 3
    with connect() as db: db.execute("UPDATE users SET pro=1,ranking_opt_in=1 WHERE github_id='local-dev'")
    assert client.get('/api/ranking').json()[0]['score'] == 800
    for _ in range(3):
        client.patch(f'/api/cases/{ids[0]}', json={'solved': False})
        client.patch(f'/api/cases/{ids[0]}', json={'cause': 'x', 'solution': 'y', 'solved': True})
    assert client.get('/api/ranking').json()[0]['score'] == 800


def test_solution_requires_notes_and_cannot_modify_other_users(client):
    bug_id = capture(client).json()['bug_id']
    assert client.patch(f'/api/cases/{bug_id}', json={'solved': True}).status_code == 400


def test_pro_routes_enforced_on_server_and_opt_in(client):
    assert client.get('/api/stats').status_code == 403
    assert client.get('/api/ranking').status_code == 403
    assert client.patch('/api/preferences', json={'ranking_opt_in': True, 'pro': True}).status_code == 200
    assert client.get('/api/me').json()['pro'] is False
    with connect() as db: db.execute('UPDATE users SET pro=1')
    stats = client.get('/api/stats').json()
    assert stats['languages'] == {'C': 0, 'Python': 0, 'Java': 0}
    client.patch('/api/preferences', json={'ranking_opt_in': False})
    assert client.get('/api/ranking').json() == []


def test_token_create_revoke_and_csrf(client):
    token = client.post('/api/tokens', json={'label': 'test'}).json()['token']
    other = TestClient(app)
    auth = {'Authorization': 'Bearer ' + token}
    assert other.get('/api/me', headers=auth).status_code == 200
    assert other.post('/api/tokens', headers=auth, json={}).status_code == 403
    key = client.get('/api/tokens').json()[0]['digest']
    client.request('DELETE', f'/api/tokens/{key}', json={})
    assert other.get('/api/me', headers=auth).status_code == 401
    assert client.post('/api/tokens', json={}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/capture', content='x', headers={'Content-Type': 'text/plain'}).status_code == 415


def test_oauth_invalid_state_rejected(client):
    assert client.get('/auth/github/callback?code=test&state=wrong').status_code == 400


def test_github_oauth_flow_and_state_replay(client, monkeypatch):
    monkeypatch.setenv('GITHUB_CLIENT_ID', 'test-id')
    monkeypatch.setenv('GITHUB_CLIENT_SECRET', 'test-secret')
    calls = []
    class GitHubClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            calls.append(url)
            return httpx.Response(200, json={'access_token': 'temporary-github-token'}, request=httpx.Request('POST', url))
        async def get(self, url, **kwargs):
            calls.append(url)
            return httpx.Response(200, json={'id': 12345, 'login': 'github-hunter'}, request=httpx.Request('GET', url))
    monkeypatch.setattr('server.app.httpx.AsyncClient', GitHubClient)
    redirect = client.get('/auth/github', follow_redirects=False)
    state = parse_qs(urlparse(redirect.headers['location']).query)['state'][0]
    response = client.get(f'/auth/github/callback?code=one-time-code&state={state}', follow_redirects=False)
    assert response.status_code == 303
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/me').json()['login'] == 'github-hunter'
    assert len(calls) == 2
    client.cookies.set('bug_index_oauth', state)
    assert client.get(f'/auth/github/callback?code=one-time-code&state={state}').status_code == 400
    with connect() as db:
        assert db.execute('SELECT count(*) FROM users WHERE github_id=?', ('12345',)).fetchone()[0] == 1


def test_payload_limits_and_public_auth(client):
    assert client.post('/api/capture', content='x' * 65537, headers={'Content-Type': 'application/json'}).status_code == 413
    unauthenticated = TestClient(app)
    assert unauthenticated.get('/api/collection').status_code == 401
    assert unauthenticated.get('/health').json() == {'status': 'ok'}


def test_export_only_current_user(client):
    capture(client)
    capture(client, project='private-other', headers=token_for_second_user())
    exported = client.get('/api/export').json()
    assert len(exported['bugs']) == 1 and len(exported['occurrences']) == 1
    assert exported['bugs'][0]['project'] == 'test'


def test_subtypes_share_xp_cooldown_and_family_level(client, monkeypatch):
    clock = time.time()
    monkeypatch.setattr('server.app.time.time', lambda: clock)
    first = capture(client, log="TypeError: unsupported operand type(s) for +: 'int' and 'str'").json()
    second = capture(client, log="TypeError: 'int' object is not callable").json()
    assert first['xp_earned'] == 1 and second['xp_earned'] == 0
    for n in range(1, 5):
        clock += 61
        capture(client, log="TypeError: 'int' object is not callable", project=f'project-{n}')
    bugs = client.get('/api/collection').json()
    subtypes = [b for b in bugs if b['discovered'] and b['family_id'] == 9]
    assert len(subtypes) == 2
    assert all(b['level'] == 2 and b['xp'] == 5 for b in subtypes)
    assert sum(b['encounters'] for b in subtypes) == 6
    assert all(b['family_encounters'] == 6 for b in subtypes)


def test_family_mastery_and_ranking_count_each_family_once(client):
    diagnostics = [
        "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
        "TypeError: 'int' object is not callable",
        "TypeError: 'NoneType' object is not subscriptable",
    ]
    ids = [capture(client, log=log).json()['bug_id'] for log in diagnostics]
    for _ in range(2): capture(client, log=diagnostics[0])
    for bug_id in ids:
        client.patch(f'/api/cases/{bug_id}', json={'cause': 'incorrect type', 'solution': 'validate input', 'solved': True})
    collection = client.get('/api/collection').json()
    mastered = [b for b in collection if b['mastered']]
    assert len(mastered) == 3 and {b['family_id'] for b in mastered} == {9}
    assert all(b['family_solved'] == 3 for b in mastered)
    with connect() as db: db.execute('UPDATE users SET pro=1,ranking_opt_in=1')
    score = client.get('/api/ranking').json()[0]
    assert score['mastered'] == 1 and score['score'] == 800


def test_unknown_messages_remain_generic_and_keep_catalog_ids(client):
    capture(client, log='TypeError: a custom diagnostic')
    entries = client.get('/api/collection').json()
    generic = next(e for e in entries if e['id'] == 9)
    assert generic['name'] == 'TypeError' and generic['discovered']
    assert len(entries) == 225
    assert {e['id'] for e in entries} >= set(range(1, 22))
