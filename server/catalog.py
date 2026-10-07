"""Deterministic classification. Never claim to diagnose errors we cannot identify."""
import hashlib
import json
import math
import re
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('errors.json').read_text(encoding='utf-8'))
BY_ID = {entry['id']: entry for entry in CATALOG}
RULES = [(entry, re.compile(entry['pattern'], re.I | re.M)) for entry in CATALOG]


def mask(text):
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(text))
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)(\b(?:api[_-]?key|password|passwd|secret|token|authorization|client_secret)\b[\"']?\s*[:=]\s*)(?:[\"'][^\"'\n]*[\"']|[^\s,;]+)", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})\b", "[REDACTED]", text)
    text = re.sub(r"(https?://|postgres(?:ql)?://|mysql://)([^\s/@]+)@", r"\1[REDACTED]@", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?i)(?:[A-Z]:[\\/]Users[\\/]|/Users/|/home/)[^/\\\s\"']+", "~/", text)
    return text[:32768]


def classify(raw, language=None):
    clean = mask(raw.replace('\r\n', '\n').replace('\r', '\n'))
    found = []
    for entry, pattern in RULES:
        if language and language != entry['language']:
            continue
        for match in pattern.finditer(clean):
            # Multiple rules can describe the same diagnostic. Prefer the specific
            # one on that line; chained errors use the final diagnostic line.
            line = clean.count('\n', 0, match.start())
            found.append((line, entry['priority'], entry['id']))
    if not found:
        return None
    _, _, number = max(found)
    entry = BY_ID[number]
    return {key: entry[key] for key in ('id', 'name', 'language', 'category', 'rarity', 'icon', 'label', 'family_id', 'family_name')} | {'log': clean}


def fingerprint(bug, project):
    # Source locations and functions remain; line numbers, addresses and messages do not.
    log = bug["log"]
    frames = re.findall(r'File "([^"\n]+)", line \d+(?:, in ([^\n]+))?', log)
    java = re.findall(r"\bat\s+([\w.$]+)\(([^():]+)(?::\d+)?\)", log)
    c = re.findall(r"([^\s:]+\.(?:c|h)):\d+(?::\d+)?", log)
    locations = [(file.replace("\\", "/"), fn) for file, fn in frames] + java + [(f, "") for f in c]
    # Without frames, normalized error text distinguishes otherwise unrelated crashes.
    fallback = re.sub(r"0x[\da-fA-F]+|\b\d+\b", "#", log)
    identity = repr((project, bug["language"], bug["name"], locations or fallback))
    return hashlib.sha256(identity.encode()).hexdigest()


def progression(xp):
    level = math.isqrt(max(0, xp) // 5) + 1
    start = 5 * (level - 1) ** 2
    target = 5 * level ** 2
    return {"level": level, "xp": xp, "level_start": start, "next_level_xp": target,
            "progress": (xp - start) / (target - start)}
