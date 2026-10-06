"""Deterministic classification. Never claim to diagnose errors we cannot identify."""
import hashlib
import math
import re

CATALOG = [
    ("NullPointerException", "Java", "Runtime", "Uncommon", "🪲", r"\bNullPointerException\b"),
    ("ArrayIndexOutOfBoundsException", "Java", "Runtime", "Uncommon", "🐜", r"\bArrayIndexOutOfBoundsException\b"),
    ("ClassNotFoundException", "Java", "Dependency", "Uncommon", "🦗", r"\bClassNotFoundException\b"),
    ("IllegalArgumentException", "Java", "Runtime", "Common", "🐞", r"\bIllegalArgumentException\b"),
    ("StackOverflowError", "Java", "Memory", "Rare", "🕷", r"\bStackOverflowError\b"),
    ("OutOfMemoryError", "Java", "Memory", "Epic", "🦂", r"\bOutOfMemoryError\b"),
    ("JavaCompileError", "Java", "Build", "Common", "🐝", r"\.java:\d+:\s*error:"),
    ("SyntaxError", "Python", "Syntax", "Common", "🐛", r"(?:^|\n)\s*(?:SyntaxError|IndentationError|TabError):"),
    ("TypeError", "Python", "Runtime", "Common", "🐞", r"(?:^|\n)\s*TypeError:"),
    ("NameError", "Python", "Runtime", "Common", "🐜", r"(?:^|\n)\s*NameError:"),
    ("IndexError", "Python", "Runtime", "Uncommon", "🪲", r"(?:^|\n)\s*IndexError:"),
    ("KeyError", "Python", "Runtime", "Uncommon", "🦗", r"(?:^|\n)\s*KeyError:"),
    ("ZeroDivisionError", "Python", "Runtime", "Common", "🐝", r"(?:^|\n)\s*ZeroDivisionError:"),
    ("ModuleNotFoundError", "Python", "Dependency", "Uncommon", "🦋", r"(?:^|\n)\s*(?:ModuleNotFoundError|ImportError):"),
    ("ValueError", "Python", "Runtime", "Common", "🐛", r"(?:^|\n)\s*ValueError:"),
    ("Segmentation Fault", "C", "Memory", "Rare", "🦂", r"segmentation fault|sigsegv|access violation"),
    ("Buffer Overflow", "C", "Memory", "Epic", "🕷", r"(?:heap|stack|global)-buffer-overflow|stack smashing detected"),
    ("Use After Free", "C", "Memory", "Epic", "🦂", r"heap-use-after-free"),
    ("Memory Leak", "C", "Memory", "Epic", "🦋", r"LeakSanitizer: detected memory leaks"),
    ("CCompileError", "C", "Build", "Common", "🐝", r"\.(?:c|h):\d+(?::\d+)?:\s*(?:fatal )?error:"),
    ("Undefined Reference", "C", "Build", "Uncommon", "🦗", r"undefined reference to|Undefined symbols for architecture"),
]


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
    clean = mask(raw)
    found = []
    for number, (name, lang, category, rarity, icon, pattern) in enumerate(CATALOG, 1):
        if language and language != lang:
            continue
        for match in re.finditer(pattern, clean, re.I):
            found.append((match.start(), number, name, lang, category, rarity, icon))
    if not found:
        return None
    _, number, name, lang, category, rarity, icon = max(found)
    return {"id": number, "name": name, "language": lang, "category": category,
            "rarity": rarity, "icon": icon, "log": clean}


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
