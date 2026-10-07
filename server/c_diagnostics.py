"""Match C tool diagnostics with source locations, stable codes and literal segments."""
import re

C_FILE = re.compile(r'(?<![\w])[^\s"\n]+\.c(?:[:(\s]|$)', re.M)
CPP_FILE = re.compile(r'(?<![\w])[^\s"\n]+\.(?:cpp|cxx|cc|hpp|hxx)(?:[:(\s]|$)', re.M)
COMPILER = re.compile(r'^[ \t]*[^"\'=\n]+\.(?:c|h):\d+(?::\d+)?:\s*(?:fatal )?error:\s*(.*)$', re.M)
MSVC = re.compile(r'^[ \t]*[^"\'=\n]+\.(?:c|h)\(\d+(?:,\d+)?\)\s*:\s*(?:fatal )?error (C\d{4}):[^\n]*$', re.M)
LINKER = re.compile(r'^[ \t]*(?:(?:[^\n:]*[/\\])?ld(?:\.lld)?(?:\.exe)?|lld-link(?:\.exe)?):\s*(?:fatal )?error:\s*(.*)$', re.M)
UBSAN = re.compile(r'^[ \t]*[^"\'=\n]+\.(?:c|h):\d+(?::\d+)?:\s*runtime error:\s*(.*)$', re.M)
ASAN = re.compile(r'^.*?ERROR: AddressSanitizer:\s*(.*)$', re.M)
MSVC_LINK = re.compile(r'^.*?\s:\s*(?:fatal )?error (LNK\d{4}):[^\n]*$', re.M)
STATIC_ID = re.compile(r'^(.*?)\s+\[([A-Za-z][\w]*)\]$')


def index(entries):
    grouped, codes = {}, {}
    for entry in entries:
        kind = entry['c_kind']
        grouped.setdefault(kind, []).append(entry)
        if entry.get('code'):
            codes[(kind, entry['code'])] = entry
    return entries, grouped, codes


def candidates(clean, language, tables, match_template):
    if language and language != 'C':
        return []
    # Header diagnostics in a C++ translation unit do not become new C species.
    if CPP_FILE.search(clean) and not C_FILE.search(clean) and language != 'C':
        return []
    if not any(pattern.search(clean) for pattern in (COMPILER, MSVC, LINKER, MSVC_LINK, UBSAN, ASAN)):
        return []
    context = language == 'C' or bool(C_FILE.search(clean))
    entries, grouped, codes = tables
    found = []
    def add(match, entry, priority):
        found.append((clean.count('\n', 0, match.start()), priority, entry['id']))
    def templates(match, kind, message):
        message = message.replace('‘', "'").replace('’', "'")
        message = re.sub(r'\s+\[-W[^\]]+\]$', '', message).strip()
        for entry in grouped.get(kind, ()):
            template = entry['message_template']
            if match_template(template, message):
                fixed = len(template.replace('\x00', ''))
                priority = 30 * fixed / (fixed + 1000) + (50 if '\x00' not in template else 0) + 1
                add(match, entry, priority)  # Below existing specific C rules (100).
    def messages(match):
        yield match[1]
        message = match[1]
        # Compiler diagnostics can contain literal newlines. Stop before source
        # excerpts, notes or a subsequent diagnostic, and keep work bounded.
        for line in clean[match.end():].lstrip('\n').splitlines()[:6]:
            if not line.strip() or re.match(r'\s*(?:\d+\s*\||\||[\^~])', line) or re.search(r'\.(?:c|h):|\b(?:error|warning|note):', line):
                break
            message += '\n' + line
            yield message
    for match in COMPILER.finditer(clean):
        static = STATIC_ID.fullmatch(match[1])
        if static:
            entry = codes.get(('cppcheck-code', static[2]))
            if entry:
                add(match, entry, 150)
            else:
                add(match, next(e for e in entries if e['id'] == 190001), 150)
        else:
            for message in messages(match):
                templates(match, 'compiler-template', message)
    for match in MSVC.finditer(clean):
        entry = codes.get(('msvc-code', match[1]))
        if entry:
            add(match, entry, 150)
    if context:
        for match in MSVC_LINK.finditer(clean):
            entry = codes.get(('msvc-linker-code', match[1]))
            if entry:
                add(match, entry, 150)
        for match in LINKER.finditer(clean):
            add(match, next(e for e in entries if e['id'] == 190000), 0.5)
            templates(match, 'linker-template', match[1])
    for match in UBSAN.finditer(clean):
        add(match, next(e for e in entries if e['id'] == 190002), 0.5)
        for message in messages(match):
            templates(match, 'ubsan-template', message)
    for match in ASAN.finditer(clean):
        templates(match, 'asan-template', match[1])
    return found
