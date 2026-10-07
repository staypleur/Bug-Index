"""Offline C snapshot builder. No parser or network dependencies at build time."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C_LOCATION = r'^[ \t]*[^"\'=\n]+\.(?:c|h):\d+(?::\d+)?:\s*(?:fatal )?error:'
MSVC_LOCATION = r'^[ \t]*[^"\'=\n]+\.(?:c|h)\(\d+(?:,\d+)?\)\s*:\s*(?:fatal )?error '
RUNTIME_LOCATION = r'^[ \t]*[^"\'=\n]+\.(?:c|h):\d+(?::\d+)?:\s*runtime error:'
SOURCE = 'https://clang.llvm.org/docs/UsersManual.html'


def c_entries(existing):
    path = ROOT / 'server/c_templates.json'
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding='utf-8'))
    baseline = [e for e in existing if e['language'] == 'C' and e['priority'] >= 100]
    roots = [
        dict(id=190000, name='CLinkError', category='Build', label='C 링크 오류',
             c_kind='linker-fallback', pattern=r'^(?:ld(?:\.lld)?|lld-link)(?:\.exe)?: error: .+$',
             sample='main.c\nld.lld: error: unspecified diagnostic'),
        dict(id=190001, name='CppcheckError', category='Analysis', label='C 정적 분석 오류',
             c_kind='static-fallback', pattern=C_LOCATION + r'.+ \[unclassifiedCheck\]$',
             sample='main.c:2:1: error: unspecified diagnostic [unclassifiedCheck]'),
        dict(id=190002, name='CSanitizerError', category='Runtime', label='C 런타임 검사 오류',
             c_kind='runtime-fallback', pattern=RUNTIME_LOCATION + r'.+$',
             sample='main.c:2:1: runtime error: unspecified diagnostic'),
    ]
    entries = []
    for root in roots:
        entries.append(root | dict(language='C', rarity='Common', icon='🐞', family_id=root['id'],
                                   family_name=root['name'], priority=0, source=SOURCE,
                                   context=r'\.c(?:[:(\s]|$)', exception='__C__'))
    for record in records:
        if record.get('excluded'):
            continue
        kind, message, code = record['kind'], record['template'], record.get('code')
        rendered = message.replace('\x00', 'sample_value')
        pattern_message = r'[^\n]*?'.join(re.escape(part).replace(r'\ ', r'\s+') for part in message.split('\x00'))
        if kind == 'compiler-template':
            sample, pattern, family = 'main.c:2:1: error: ' + rendered, C_LOCATION + r'\s*' + pattern_message + r'\s*$', 20
            package = 'GCC / Clang'
        elif kind == 'msvc-code':
            sample, pattern, family = f'main.c(2,1): error {code}: example diagnostic', MSVC_LOCATION + re.escape(code) + r':', 20
            package = 'MSVC'
        elif kind == 'cppcheck-code':
            sample, pattern, family = f'main.c:2:1: error: {rendered} [{code}]', C_LOCATION + r'.+ \[' + re.escape(code) + r'\]$', 190001
            package = 'Cppcheck'
        elif kind == 'msvc-linker-code':
            sample, pattern, family = f'main.c\nmain.obj : error {code}: example diagnostic', r'^.*(?:fatal )?error ' + re.escape(code) + r':', 21 if code in ('LNK2001', 'LNK2019', 'LNK1120') else 190000
            package = 'MSVC linker'
        elif kind == 'linker-template':
            sample, pattern, family = 'main.c\nld.lld: error: ' + rendered, r'^ld\.lld: error:\s*' + pattern_message + r'\s*$', 190000
            package = 'LLD'
        elif kind == 'asan-template':
            sample, pattern, family = 'ERROR: AddressSanitizer: ' + rendered, r'ERROR: AddressSanitizer:\s*' + pattern_message + r'\s*$', 190002
            package = 'ASan'
        else:
            sample, pattern, family = 'main.c:2:1: runtime error: ' + rendered, RUNTIME_LOCATION + r'\s*' + pattern_message + r'\s*$', 190002
            package = 'UBSan'
        # Existing specific types retain precedence and identity. Such aliases
        # stay in the source audit but do not inflate the species count.
        if any(re.search(e['pattern'], sample, re.I | re.M) for e in baseline):
            continue
        parent = next(e for e in existing + entries if e['id'] == family)
        entries.append(dict(id=record['id'], name=f'C.{kind}.{code or record["key"][:12]}',
                            language='C', category='Analysis' if kind == 'cppcheck-code' else 'Memory' if kind == 'asan-template' else 'Runtime' if kind == 'ubsan-template' else 'Build',
                            label=f'{code}: {message}' if code else message.replace('\x00', '…'),
                            icon='🐝', rarity='Uncommon', family_id=family, family_name=parent['name'],
                            sample=sample, pattern=pattern, priority=50, source=record['source'],
                            package=package, verification='source-template', template_key=record['key'],
                            message_template=message, c_kind=kind, code=code,
                            context=r'\.c(?:[:(\s]|$)', exception='__C__', tools=record['tools']))
    return entries
