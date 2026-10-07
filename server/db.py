import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect():
    path = Path(os.environ.get("BUG_INDEX_DB", "data/bug-index.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, github_id TEXT UNIQUE NOT NULL,
          login TEXT NOT NULL, pro INTEGER NOT NULL DEFAULT 0,
          ranking_opt_in INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS sessions (
          digest TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          expires REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS oauth_states (
          digest TEXT PRIMARY KEY, expires REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tokens (
          digest TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          label TEXT NOT NULL, created REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bugs (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          species INTEGER NOT NULL, fingerprint TEXT NOT NULL, project TEXT NOT NULL,
          first_seen REAL NOT NULL, last_seen REAL NOT NULL,
          cause TEXT NOT NULL DEFAULT '', solution TEXT NOT NULL DEFAULT '',
          memo TEXT NOT NULL DEFAULT '', solved_at REAL,
          UNIQUE(user_id, fingerprint)
        );
        CREATE TABLE IF NOT EXISTS occurrences (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          bug_id INTEGER NOT NULL REFERENCES bugs(id), request_id TEXT NOT NULL,
          log TEXT NOT NULL, occurred_at REAL NOT NULL, xp INTEGER NOT NULL,
          UNIQUE(user_id, request_id)
        );
        CREATE INDEX IF NOT EXISTS bugs_owner ON bugs(user_id, species);
        CREATE INDEX IF NOT EXISTS occurrences_bug ON occurrences(bug_id, occurred_at);
        CREATE TABLE IF NOT EXISTS unknown_bugs (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          fingerprint TEXT NOT NULL, project TEXT NOT NULL, language TEXT NOT NULL,
          diagnostic TEXT NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL,
          cause TEXT NOT NULL DEFAULT '', solution TEXT NOT NULL DEFAULT '',
          memo TEXT NOT NULL DEFAULT '', solved_at REAL,
          resolved_bug_id INTEGER REFERENCES bugs(id), UNIQUE(user_id,fingerprint)
        );
        CREATE TABLE IF NOT EXISTS unknown_occurrences (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          unknown_id INTEGER NOT NULL REFERENCES unknown_bugs(id), request_id TEXT NOT NULL,
          log TEXT NOT NULL, occurred_at REAL NOT NULL, UNIQUE(user_id,request_id)
        );
        CREATE INDEX IF NOT EXISTS unknown_owner ON unknown_bugs(user_id,last_seen);
        CREATE INDEX IF NOT EXISTS unknown_occurrence_bug ON unknown_occurrences(unknown_id,occurred_at);
        ''')
        columns = {row['name'] for row in db.execute('PRAGMA table_info(bugs)')}
        if 'family_id' not in columns:
            db.execute('ALTER TABLE bugs ADD COLUMN family_id INTEGER')
            # The initial catalog only contained root types. Preserve their
            # IDs, XP, solutions and fingerprints when adding subdivisions.
            db.execute('UPDATE bugs SET family_id=species WHERE family_id IS NULL')
        db.execute('CREATE INDEX IF NOT EXISTS bugs_family ON bugs(user_id,family_id)')
