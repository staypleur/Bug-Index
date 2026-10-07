"""Deterministic classification. Never claim to diagnose errors we cannot identify."""
import hashlib
import json
import math
import re
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('errors.json').read_text(encoding='utf-8'))
BY_ID = {entry['id']: entry for entry in CATALOG}
RULES = [(entry, re.compile(entry['pattern'], re.I | re.M)) for entry in CATALOG]
CORE_RULES = [(entry, pattern) for entry, pattern in RULES if not entry.get('context')]
C_RULES = [entry for entry in CATALOG if entry.get('c_kind')]
from server.c_diagnostics import index as c_index
C_INDEX = c_index(C_RULES)
LIBRARY_RULES = {}
for entry, pattern in RULES:
    if entry.get('context') and not entry.get('c_kind'):
        LIBRARY_RULES.setdefault((entry['context'], entry['exception']), []).append((entry, pattern))
CONTEXTS = {entry['context']: re.compile(entry['context'], re.M) for entry in CATALOG if entry.get('context') and not entry.get('c_kind')}
PREFIXES = [re.compile(pattern, re.M) for pattern in json.loads(Path(__file__).with_name('diagnostic-prefixes.json').read_text(encoding='utf-8'))]
JAVA_TRACE = re.compile(r'^[ \t]*(?:(?:Exception in thread "[^"\n]+"|Caused by:|Suppressed:)\s+)?((?:[\w$]+\.)+[\w$]*(?:Exception|Error))(?::[ \t]*([^\n]*))?$', re.M)
JAVA_FRAMES = re.compile(r'^[ \t]*at (?:[^\s/]+/)?([\w.$<>]+)\([^\n]+\)', re.M)
JAVA_HELPER_FRAMES = ('java.util.Objects.requireNonNull', 'org.springframework.util.Assert.', 'com.google.common.base.Preconditions.')
DETECTORS = [(entry, re.compile(entry['pattern'], re.M), re.compile(entry['context'], re.M) if entry.get('context') else None)
             for entry in json.loads(Path(__file__).with_name('diagnostics.json').read_text(encoding='utf-8'))]
FIELDS = ('id', 'name', 'language', 'category', 'rarity', 'icon', 'label', 'family_id', 'family_name')


def diagnostic(raw, language=None):
    """Recognize evidence of an error, without assigning a catalog species."""
    clean = normalize(raw)
    found = []
    for entry, pattern, context in DETECTORS:
        if language and language != entry['language']:
            continue
        if context and not context.search(clean) and not (entry.get('requires_c_context') and language == 'C'):
            continue
        for match in pattern.finditer(clean):
            name = match.group().split(':', 1)[0].rsplit('.', 1)[-1].strip()
            if name.endswith('Warning') or name in ('KeyboardInterrupt', 'SystemExit', 'StopIteration', 'StopAsyncIteration'):
                continue
            found.append((match.start(), entry['language'], match.group().strip()))
    if not found:
        return None
    position, detected_language, message = max(found)
    return {'language': detected_language, 'log': clean, 'diagnostic': message,
            'line': clean.count('\n', 0, position)}


def public_entry(entry):
    return {key: entry[key] for key in FIELDS} | {key: entry[key] for key in ('package', 'source', 'verification') if key in entry}


def template_matches(template, message):
    """Literal segments and arbitrary values, with no regex backtracking."""
    parts = template.casefold().split('\x00')
    message = re.sub(r'\s+', ' ', message.strip()).casefold()
    if len(parts) == 1:
        return parts[0] == message
    if not message.startswith(parts[0]) or not message.endswith(parts[-1]):
        return False
    position, end = len(parts[0]), len(message) - len(parts[-1])
    for part in parts[1:-1]:
        found = message.find(part, position, end)
        if found < 0:
            return False
        position = found + len(part)
    return position <= end


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


def normalize(raw):
    clean = mask(raw.replace('\r\n', '\n').replace('\r', '\n'))
    for prefix in PREFIXES:
        clean = prefix.sub('', clean)
    return clean


def classify(raw, language=None):
    clean = normalize(raw)
    found = []
    if C_RULES:
        from server.c_diagnostics import candidates as c_candidates
        found.extend(c_candidates(clean, language, C_INDEX, template_matches))
    contexts = {context for context, pattern in CONTEXTS.items() if pattern.search(clean)}
    exception_names = set(re.findall(r'^[ \t]*(?:[|+]\s*)?(\w+):', clean, re.M))
    candidates = CORE_RULES
    exception_lines = list(re.finditer(r'^[ \t]*(?:[|+]\s*)?(\w+):[ \t]*([^\n]*)$', clean, re.M))
    for context in contexts:
        for exception in exception_names:
            for entry, _ in LIBRARY_RULES.get((context, exception), ()):
                if language and language != entry['language']:
                    continue
                for match in exception_lines:
                    if match[1] != exception:
                        continue
                    messages = (match[2], clean[match.start(2):])
                    if any(template_matches(entry['message_template'], message) for message in messages):
                        found.append((clean.count('\n', 0, match.start()), entry['priority'], entry['id']))
    traces = list(JAVA_TRACE.finditer(clean))
    for index, trace in enumerate(traces):
        qualified, message = trace[1], trace[2] or ''
        end = traces[index + 1].start() if index + 1 < len(traces) else len(clean)
        continuation = clean[trace.end():end]
        frames = list(JAVA_FRAMES.finditer(continuation))
        if not frames:
            continue  # A Java library origin cannot be inferred from an exception name.
        message += continuation[:frames[0].start()]
        names = [frame[1] for frame in frames]
        for context in contexts:
            for entry, _ in LIBRARY_RULES.get((context, qualified), ()):
                if entry['language'] != 'Java' or (language and language != 'Java'):
                    continue
                origins = names.copy()
                if entry.get('kind') == 'precondition-call':
                    while origins and origins[0].startswith(JAVA_HELPER_FRAMES):
                        origins.pop(0)
                if not origins or not origins[0].startswith(tuple(entry['origin_prefixes'])):
                    continue
                if template_matches(entry['message_template'], message):
                    origin = max(len(prefix) for prefix in entry['origin_prefixes'] if origins[0].startswith(prefix))
                    module = 1000 if origins[0].startswith(entry.get('origin_module', '') + '.') else 0
                    exact = 1000 if '\x00' not in entry['message_template'] else 0
                    found.append((clean.count('\n', 0, trace.start()), origin * 10000 + module + exact + entry['priority'], entry['id']))
    for entry, pattern in candidates:
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
    evidence = diagnostic(clean, language)
    if evidence and evidence['line'] > max(found)[0]:
        return None  # Do not misclassify the final unknown error as its earlier cause.
    entry = BY_ID[number]
    return public_entry(entry) | {'log': clean}


def fingerprint(bug, project):
    # Source locations and functions remain; line numbers, addresses and messages do not.
    log = bug["log"]
    frames = re.findall(r'File "([^"\n]+)", line \d+(?:, in ([^\n]+))?', log)
    java = re.findall(r"\bat\s+(?:[^\s/]+/)?([\w.$<>]+)\(([^():]+)(?::\d+)?\)", log)
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
