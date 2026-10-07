import hashlib
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .catalog import CATALOG, classify, fingerprint, mask, progression
from .db import connect, initialize

BASE = os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/")
SECURE = BASE.startswith("https://")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@asynccontextmanager
async def lifespan(app):
    initialize()
    if os.environ.get("DEV_LOGIN") == "1" and urlparse(BASE).hostname not in ("localhost", "127.0.0.1"):
        raise RuntimeError("DEV_LOGIN is allowed only on localhost")
    yield


app = FastAPI(title="Bug Index", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.middleware("http")
async def security(request, call_next):
    if request.method in ("POST", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin and origin != BASE:
            return JSONResponse({"detail": "허용되지 않은 요청 출처입니다."}, status_code=403)
        if "application/json" not in request.headers.get("content-type", ""):
            return JSONResponse({"detail": "JSON 요청이 필요합니다."}, status_code=415)
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "잘못된 요청입니다."}, status_code=400)
        if length > 65536:
            return JSONResponse({"detail": "로그 크기가 너무 큽니다."}, status_code=413)
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 65536:
                return JSONResponse({"detail": "로그 크기가 너무 큽니다."}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if request.url.path.startswith(("/api/", "/auth/")):
        response.headers["Cache-Control"] = "no-store"
    return response


def user(request: Request):
    auth = request.headers.get("authorization", "")
    with connect() as db:
        if auth.startswith("Bearer "):
            row = db.execute("SELECT u.* FROM users u JOIN tokens t ON t.user_id=u.id WHERE t.digest=?", (digest(auth[7:]),)).fetchone()
        else:
            session = request.cookies.get("bug_index_session", "")
            row = db.execute("SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.digest=? AND s.expires>?", (digest(session), time.time())).fetchone()
    if not row:
        raise HTTPException(401, "GitHub 로그인이 필요합니다.")
    return dict(row)


def browser_user(request: Request, current=Depends(user)):
    if request.headers.get("authorization"):
        raise HTTPException(403, "웹 로그인으로만 가능한 작업입니다.")
    return current


def pro(current=Depends(user)):
    if not current["pro"]:
        raise HTTPException(403, "고급 통계와 랭킹은 Pro 기능입니다. 결제는 아직 준비 중입니다.")
    return current


def session_response(uid):
    value = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        db.execute("INSERT INTO sessions VALUES(?,?,?)", (digest(value), uid, time.time() + 7 * 86400))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("bug_index_session", value, httponly=True, secure=SECURE, samesite="lax", max_age=7 * 86400)
    return response


@app.get("/health")
def health():
    with connect() as db:
        db.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {"github_configured": bool(os.environ.get("GITHUB_CLIENT_ID") and os.environ.get("GITHUB_CLIENT_SECRET")),
            "dev_login": os.environ.get("DEV_LOGIN") == "1", "billing_enabled": False}


@app.get("/auth/github")
def github_login():
    client = os.environ.get("GITHUB_CLIENT_ID")
    if not client or not os.environ.get("GITHUB_CLIENT_SECRET"):
        raise HTTPException(503, "운영자가 GitHub OAuth 설정을 완료해야 합니다.")
    state = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("DELETE FROM oauth_states WHERE expires<?", (time.time(),))
        db.execute("INSERT INTO oauth_states VALUES(?,?)", (digest(state), time.time() + 600))
    response = RedirectResponse("https://github.com/login/oauth/authorize?" + urlencode({"client_id": client, "redirect_uri": BASE + "/auth/github/callback", "state": state}))
    response.set_cookie("bug_index_oauth", state, httponly=True, secure=SECURE, samesite="lax", max_age=600)
    return response


@app.get("/auth/github/callback")
async def callback(request: Request, code: str = "", state: str = ""):
    cookie = request.cookies.get("bug_index_oauth", "")
    if not state or not cookie or not secrets.compare_digest(cookie, state) or not code:
        raise HTTPException(400, "로그인 검증에 실패했습니다. 다시 로그인해주세요.")
    with connect() as db:
        row = db.execute("DELETE FROM oauth_states WHERE digest=? AND expires>? RETURNING digest", (digest(state), time.time())).fetchone()
    if not row:
        raise HTTPException(400, "로그인 요청이 만료되었습니다.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            result = await client.post("https://github.com/login/oauth/access_token", headers={"Accept": "application/json"}, json={"client_id": os.environ.get("GITHUB_CLIENT_ID"), "client_secret": os.environ.get("GITHUB_CLIENT_SECRET"), "code": code, "redirect_uri": BASE + "/auth/github/callback"})
            result.raise_for_status()
            access = result.json().get("access_token")
            if not access:
                raise ValueError("Missing access token")
            profile = await client.get("https://api.github.com/user", headers={"Authorization": "Bearer " + access, "Accept": "application/vnd.github+json", "User-Agent": "Bug-Index"})
            profile.raise_for_status()
            info = profile.json()
            github_id, login = str(info["id"]), info["login"]
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(502, "GitHub 인증을 완료하지 못했습니다. 다시 시도해주세요.")
    with connect() as db:
        db.execute("INSERT INTO users(github_id,login) VALUES(?,?) ON CONFLICT(github_id) DO UPDATE SET login=excluded.login", (github_id, login))
        uid = db.execute("SELECT id FROM users WHERE github_id=?", (github_id,)).fetchone()[0]
    response = session_response(uid)
    response.delete_cookie("bug_index_oauth")
    return response


@app.get("/auth/dev")
def dev_login(request: Request):
    if os.environ.get("DEV_LOGIN") != "1" or request.client.host not in ("127.0.0.1", "::1", "testclient"):
        raise HTTPException(404)
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO users(github_id,login) VALUES('local-dev','local-developer')")
        uid = db.execute("SELECT id FROM users WHERE github_id='local-dev'").fetchone()[0]
    return session_response(uid)


@app.post("/api/logout")
def logout(request: Request, current=Depends(browser_user)):
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE digest=?", (digest(request.cookies.get("bug_index_session", "")),))
    response = JSONResponse({"ok": True})
    response.delete_cookie("bug_index_session")
    return response


@app.get("/api/me")
def me(current=Depends(user)):
    return {"login": current["login"], "pro": bool(current["pro"]), "ranking_opt_in": bool(current["ranking_opt_in"])}


class Preferences(BaseModel):
    ranking_opt_in: bool


@app.patch("/api/preferences")
def preferences(body: Preferences, current=Depends(browser_user)):
    with connect() as db:
        db.execute("UPDATE users SET ranking_opt_in=? WHERE id=?", (int(body.ranking_opt_in), current["id"]))
    return {"ok": True}


class TokenInput(BaseModel):
    label: str = Field(default="VS Code", min_length=1, max_length=80)


@app.get("/api/tokens")
def tokens(current=Depends(browser_user)):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT digest,label,created FROM tokens WHERE user_id=? ORDER BY created DESC", (current["id"],))]


@app.post("/api/tokens")
def create_token(body: TokenInput, current=Depends(browser_user)):
    token = "bidx_" + secrets.token_urlsafe(32)
    with connect() as db:
        if db.execute("SELECT count(*) FROM tokens WHERE user_id=?", (current["id"],)).fetchone()[0] >= 10:
            raise HTTPException(400, "토큰은 최대 10개까지 만들 수 있습니다.")
        db.execute("INSERT INTO tokens VALUES(?,?,?,?)", (digest(token), current["id"], body.label, time.time()))
    return {"token": token}


@app.delete("/api/tokens/{token_digest}")
def revoke_token(token_digest: str, current=Depends(browser_user)):
    with connect() as db:
        db.execute("DELETE FROM tokens WHERE digest=? AND user_id=?", (token_digest, current["id"]))
    return {"ok": True}


class Capture(BaseModel):
    log: str = Field(min_length=1, max_length=32768)
    project: str = Field(default="untitled", min_length=1, max_length=120)
    language: str | None = Field(default=None, pattern="^(C|Python|Java)$")
    request_id: str = Field(min_length=8, max_length=100)


@app.post("/api/capture")
def capture(body: Capture, current=Depends(user)):
    classified = classify(body.log, body.language)
    if not classified:
        return {"collected": False, "reason": "지원하는 오류 패턴을 찾지 못했습니다."}
    now = time.time()
    project = mask(body.project)
    key = fingerprint(classified, project)
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT bug_id FROM occurrences WHERE user_id=? AND request_id=?", (current["id"], body.request_id)).fetchone()
        if previous:
            return {"collected": True, "duplicate": True, "bug_id": previous[0]}
        if db.execute("SELECT count(*) FROM occurrences WHERE user_id=? AND occurred_at>?", (current["id"], now - 60)).fetchone()[0] >= 60:
            raise HTTPException(429, "수집 요청이 너무 많습니다. 잠시 후 재시도해주세요.")
        existing = db.execute("SELECT id FROM bugs WHERE user_id=? AND fingerprint=?", (current["id"], key)).fetchone()
        db.execute("INSERT INTO bugs(user_id,species,family_id,fingerprint,project,first_seen,last_seen) VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,fingerprint) DO UPDATE SET last_seen=excluded.last_seen", (current["id"], classified["id"], classified['family_id'], key, project, now, now))
        bug_id = db.execute("SELECT id FROM bugs WHERE user_id=? AND fingerprint=?", (current["id"], key)).fetchone()[0]
        # Store encounters, but grant at most one XP per species each minute.
        recent = db.execute("SELECT 1 FROM occurrences o JOIN bugs b ON b.id=o.bug_id WHERE o.user_id=? AND b.family_id=? AND o.xp=1 AND o.occurred_at>? LIMIT 1", (current["id"], classified['family_id'], now - 60)).fetchone()
        xp = 0 if recent else 1
        db.execute("INSERT INTO occurrences(user_id,bug_id,request_id,log,occurred_at,xp) VALUES(?,?,?,?,?,?)", (current["id"], bug_id, body.request_id, classified["log"], now, xp))
    display = classified['family_name'] + ' · ' + classified['label'] if classified['family_id'] != classified['id'] else classified['name']
    return {"collected": True, "bug_id": bug_id, "new_case": not bool(existing), "species": display, "xp_earned": xp}


def collection(uid):
    with connect() as db:
        rows = db.execute('''SELECT b.species, count(DISTINCT b.id) cases,
          count(o.id) encounters, coalesce(sum(o.xp),0) xp,
          count(DISTINCT CASE WHEN b.solved_at IS NOT NULL THEN b.id END) solved,
          min(b.first_seen) first_seen, max(b.last_seen) last_seen
          FROM bugs b LEFT JOIN occurrences o ON o.bug_id=b.id
          WHERE b.user_id=? GROUP BY b.species''', (uid,)).fetchall()
        families = {r['family_id']: dict(r) for r in db.execute('''SELECT b.family_id,
          count(o.id) encounters,coalesce(sum(o.xp),0) xp,
          count(DISTINCT CASE WHEN b.solved_at IS NOT NULL THEN b.id END) solved
          FROM bugs b LEFT JOIN occurrences o ON o.bug_id=b.id
          WHERE b.user_id=? GROUP BY b.family_id''', (uid,))}
    discovered = {row["species"]: dict(row) for row in rows}
    result = []
    for entry in CATALOG:
        number = entry['id']
        state = discovered.get(number, {"cases": 0, "encounters": 0, "xp": 0, "solved": 0})
        family = families.get(entry['family_id'], {'encounters': 0, 'xp': 0, 'solved': 0})
        result.append({key: entry[key] for key in ('id', 'name', 'language', 'category', 'rarity', 'icon', 'label', 'family_id', 'family_name')} |
                      {**state, **progression(family['xp']), 'family_encounters': family['encounters'],
                       'family_solved': family['solved'], "discovered": number in discovered,
                       "mastered": number in discovered and family['encounters'] >= 5 and family['solved'] >= 3})
    return result


@app.get("/api/collection")
def get_collection(current=Depends(user)):
    return collection(current["id"])


@app.get("/api/species/{species_id}/cases")
def cases(species_id: int, current=Depends(user)):
    with connect() as db:
        rows = db.execute('''SELECT b.*,count(o.id) encounters FROM bugs b LEFT JOIN occurrences o ON o.bug_id=b.id
          WHERE b.user_id=? AND b.species=? GROUP BY b.id ORDER BY b.last_seen DESC''', (current["id"], species_id)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item.pop("user_id")
            item["occurrences"] = [dict(o) for o in db.execute("SELECT id,log,occurred_at,xp FROM occurrences WHERE bug_id=? ORDER BY occurred_at DESC LIMIT 20", (row["id"],))]
            result.append(item)
        return result


class Solution(BaseModel):
    cause: str = Field(default="", max_length=4000)
    solution: str = Field(default="", max_length=8000)
    memo: str = Field(default="", max_length=4000)
    solved: bool = False


@app.patch("/api/cases/{bug_id}")
def save_solution(bug_id: int, body: Solution, current=Depends(user)):
    cause, solution, memo = mask(body.cause).strip(), mask(body.solution).strip(), mask(body.memo).strip()
    if body.solved and (not cause or not solution):
        raise HTTPException(400, "해결 완료에는 원인과 해결 방법이 필요합니다.")
    with connect() as db:
        previous = db.execute("SELECT solved_at FROM bugs WHERE id=? AND user_id=?", (bug_id, current["id"])).fetchone()
        if not previous:
            raise HTTPException(404, "버그를 찾을 수 없습니다.")
        solved_at = (previous[0] or time.time()) if body.solved else None
        db.execute("UPDATE bugs SET cause=?,solution=?,memo=?,solved_at=? WHERE id=? AND user_id=?", (cause, solution, memo, solved_at, bug_id, current["id"]))
    return {"ok": True}


@app.get("/api/stats")
def stats(current=Depends(pro)):
    with connect() as db:
        days = [dict(r) for r in db.execute("SELECT strftime('%Y-%m-%d',occurred_at,'unixepoch') day,count(*) count FROM occurrences WHERE user_id=? AND occurred_at>? GROUP BY day ORDER BY day", (current["id"], time.time() - 30 * 86400))]
        projects = [dict(r) for r in db.execute("SELECT b.project,count(o.id) encounters FROM bugs b JOIN occurrences o ON o.bug_id=b.id WHERE b.user_id=? GROUP BY b.project ORDER BY encounters DESC", (current["id"],))]
    species = collection(current["id"])
    languages = {lang: sum(s["encounters"] for s in species if s["language"] == lang) for lang in ("C", "Python", "Java")}
    return {"days": days, "projects": projects, "languages": languages, "top_errors": sorted([s for s in species if s["discovered"]], key=lambda s: s["encounters"], reverse=True)[:5], "timezone": "UTC"}


@app.get("/api/ranking")
def ranking(current=Depends(pro)):
    with connect() as db:
        # Aggregate counts in SQL rather than exposing any user's logs or projects.
        rows = db.execute('''WITH per_species AS (
          SELECT b.user_id,b.family_id,count(o.id) encounters,
          count(DISTINCT CASE WHEN b.solved_at IS NOT NULL THEN b.id END) solved
          FROM bugs b LEFT JOIN occurrences o ON o.bug_id=b.id GROUP BY b.user_id,b.family_id
        ), scores AS (
          SELECT user_id,sum(solved) solved,
          sum(CASE WHEN encounters>=5 AND solved>=3 THEN 1 ELSE 0 END) mastered
          FROM per_species GROUP BY user_id
        ) SELECT u.login,coalesce(s.solved,0) solved,coalesce(s.mastered,0) mastered,
          coalesce(s.solved,0)*100+coalesce(s.mastered,0)*500 score
          FROM users u LEFT JOIN scores s ON s.user_id=u.id WHERE u.ranking_opt_in=1
          ORDER BY score DESC,u.login COLLATE NOCASE ASC LIMIT 100''').fetchall()
    return [{"rank": index + 1, **dict(row)} for index, row in enumerate(rows)]


@app.get("/api/export")
def export(current=Depends(browser_user)):
    with connect() as db:
        bugs = [dict(r) for r in db.execute("SELECT * FROM bugs WHERE user_id=?", (current["id"],))]
        occurrences = [dict(r) for r in db.execute("SELECT * FROM occurrences WHERE user_id=?", (current["id"],))]
    for row in bugs + occurrences:
        row.pop("user_id", None)
    return JSONResponse({"version": 1, "login": current["login"], "bugs": bugs, "occurrences": occurrences}, headers={"Content-Disposition": 'attachment; filename="bug-index-export.json"'})


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "web", html=True), name="web")
