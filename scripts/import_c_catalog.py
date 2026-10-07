"""Import actual C diagnostics; upstream code is read, never executed.

GCC: C frontend error calls. Clang: C lexer and an audited parser subset.
Cppcheck: error-severity IDs in C-relevant checks. MSVC: audited C error codes.
Published snapshot IDs are append-only. Warnings and C++-only checks are excluded.
"""
import ast
import hashlib
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tree_sitter import Language, Parser
import tree_sitter_cpp
from scripts.import_library_catalog import request

ROOT = Path(__file__).resolve().parent.parent
SLOT = '\x00'
REPOS = {'GCC': 'gcc-mirror/gcc', 'Clang': 'llvm/llvm-project',
         'Cppcheck': 'cppcheck-opensource/cppcheck', 'MSVC': 'MicrosoftDocs/cpp-docs',
         'LLD': 'llvm/llvm-project'}
COMMITS = {'GCC': '302af96357ff5e3a660e9441166e8c1f1966f45a',
           'Clang': 'bd1c9e3efed65cfcc137a183450e56dac3eb9ff4',
           'LLD': 'bd1c9e3efed65cfcc137a183450e56dac3eb9ff4',
           'Cppcheck': '9c1b4eb232f4ddac74652dec8c9d7e251ba218a2',
           'MSVC': 'd60f66970c0eea43aed9addf362da88747c9d154'}
CLANG_PARSE = set('''err_asm_qualifier_ignored err_global_asm_qualifier_ignored err_asm_empty
err_msasm_unsupported_arch err_msasm_unable_to_create_target err_gnu_inline_asm_disabled
err_asm_duplicate_qual err_empty_enum err_enumerator_list_missing_comma
err_enumerator_unnamed_no_def err_duplicate_default_assoc err_c11_noreturn_misplaced
err_stmtexpr_file_scope err_expected_equal_designator err_expected_expression
err_expected_type err_expected_external_declaration err_extraneous_closing_brace
err_expected_semi_declaration err_expected_semi_decl_list err_expected_member_name_or_semi
err_function_declared_typedef err_unexpected_semi err_expected_fn_body
err_expected_statement err_expected_lparen_after err_expected_rparen_after
err_expected_semi_after_stmt err_expected_semi_after_expr err_expected_identifier
err_expected_string_literal err_expected_asm_operand err_expected_colon
err_expected_comma err_expected_semi_after err_expected err_duplicate_declspec
err_invalid_decl_specifier err_invalid_sign_spec err_invalid_width_spec
err_invalid_complex_spec err_invalid_storage_class_in_func_decl
err_expected_parameter_declarator err_expected_type_name_after_typeof
err_expected_semi_after_static_assert err_static_assert_without_message
err_type_specifier_missing err_expected_semi_after_struct
err_c2y_labeled_break_continue err_c2y_first_condition_clause_is_not_declaration
err_c2y_multiple_declarations'''.split())
CPP_FILES = ['checkbufferoverrun', 'checkmemoryleak', 'checknullpointer',
             'checkuninitvar', 'checkfunctions', 'checkother', 'checkstring',
             'checktype', 'check64bit', 'checkvaarg', 'checkio', 'checksizeof']
MSVC_CODES = set('''C1001 C1002 C1003 C1004 C1007 C1008 C1009 C1010 C1012 C1013
C1014 C1016 C1017 C1018 C1019 C1020 C1021 C1022 C1023 C1024 C1026 C1027 C1028
C1029 C1033 C1034 C1035 C1037 C1038 C1041 C1047 C1051 C1057 C1060 C1061 C1070
C1071 C1075 C1076 C1083 C1090 C1092 C1900 C1902 C2001 C2003 C2004 C2005 C2006
C2007 C2008 C2009 C2010 C2011 C2013 C2014 C2015 C2016 C2017 C2018 C2019 C2020
C2021 C2022 C2023 C2024 C2025 C2026 C2028 C2029 C2030 C2031 C2032 C2033 C2034
C2035 C2036 C2037 C2038 C2039 C2040 C2041 C2042 C2043 C2044 C2045 C2046 C2047
C2048 C2049 C2050 C2051 C2052 C2053 C2054 C2055 C2056 C2057 C2058 C2059 C2060
C2061 C2062 C2063 C2064 C2065 C2066 C2067 C2068 C2069 C2070 C2071 C2072 C2073
C2074 C2075 C2076 C2077 C2078 C2079 C2080 C2081 C2082 C2084 C2085 C2086 C2087
C2088 C2090 C2091 C2092 C2093 C2094 C2095 C2096 C2097 C2098 C2099 C2100 C2101
C2102 C2103 C2104 C2105 C2106 C2107 C2108 C2109 C2110 C2111 C2112 C2113 C2114
C2115 C2116 C2117 C2118 C2120 C2121 C2122 C2124 C2125 C2126 C2127 C2128 C2130
C2131 C2132 C2133 C2134 C2135 C2136 C2137 C2138 C2142 C2143 C2144 C2145 C2146
C2147 C2148 C2149 C2150 C2151 C2152 C2153 C2154 C2155 C2156 C2157 C2158 C2159
C2160 C2162 C2163 C2164 C2165 C2166 C2167 C2168 C2169 C2170 C2171 C2172 C2173
C2174 C2175 C2176 C2177 C2181 C2182 C2183 C2184 C2185 C2186 C2190 C2193 C2194
C2196 C2197 C2198 C2199 C2200 C2201 C2202 C2203 C2204 C2205 C2206 C2207 C2208
C2209 C2210 C2211 C2212 C2213 C2214 C2215 C2216 C2217 C2218 C2219 C2220 C2221
C2222 C2223 C2224 C2226 C2230 C2231 C2232 C2233 C2234 C2235 C2236 C2237 C2238
C2239 C2240 C2241 C2242 C2243 C2244'''.split())
# Audited shared C diagnostics only; documents discussing C++ concepts are rejected.
CPP_ONLY = re.compile(r'c\+\+|\b(?:class|template|namespace|constructor|destructor|overload|lambda|virtual|friend|constexpr|consteval|reference|new|delete|throw|catch|try|exception|operator|member function|access specifier)\b', re.I)


def fetch(tool, path):
    cache = ROOT / 'artifacts/c-sources' / tool / path
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        cache.write_bytes(request(f'https://raw.githubusercontent.com/{REPOS[tool]}/{COMMITS[tool]}/{path}'))
    return cache.read_text(encoding='utf-8')


def walk(node):
    todo = [node]
    while todo:
        node = todo.pop()
        yield node
        todo.extend(reversed(node.named_children))


def text(node, source):
    return source[node.start_byte:node.end_byte].decode('utf-8') if node else ''


def string(node, source):
    if node.type == 'string_literal':
        raw = text(node, source)
        if not raw.startswith('"'):
            return None
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return None
    if node.type == 'concatenated_string':
        parts = [string(child, source) for child in node.named_children]
        return ''.join(parts) if all(part is not None for part in parts) else None
    if node.type == 'call_expression':
        owner = text(node.child_by_field_name('function'), source)
        args = node.child_by_field_name('arguments')
        if owner in ('_', 'G_', 'N_', 'gettext') and args and len(args.named_children) == 1:
            return string(args.named_children[0], source)
    return None


def gcc_template(message):
    message = message.replace('%<', "'").replace('%>', "'").replace('%%', '\x01')
    message = re.sub(r'%q(?:[A-Za-z])', "'" + SLOT + "'", message)
    message = re.sub(r'%(?:\+|#)?(?:z|ll|l|w|h|t)?(?:\.\*|\.\d+)?[A-Za-z]', SLOT, message)
    if '%' in message:
        return None
    return clean(message.replace('\x01', '%'))


def clean(message):
    return re.sub(r'\s+', ' ', message).strip().replace('‘', "'").replace('’', "'")


def eligible(message, minimum=12):
    fixed = message.replace(SLOT, '')
    return len(fixed) >= minimum and len(message) <= 700 and '\n' not in message


def gcc_calls(contents):
    source = contents.encode()
    tree = Parser(Language(tree_sitter_cpp.language())).parse(source)
    # GCC source extensions can create unrelated parser errors. Each accepted
    # call and string must nevertheless have a fully parsed subtree.
    result = []
    for node in walk(tree.root_node):
        if node.type != 'call_expression' or node.has_error:
            continue
        name = text(node.child_by_field_name('function'), source)
        args = node.child_by_field_name('arguments')
        if name not in ('error', 'error_at', 'fatal_error', 'c_parser_error') or not args:
            continue
        ancestor, excluded = node.parent, False
        while ancestor:
            if ancestor.type == 'function_definition':
                signature = text(ancestor.child_by_field_name('declarator'), source)
                if re.search(r'objc|objective', signature, re.I):
                    excluded = True
                break
            if ancestor.type in ('if_statement', 'case_statement'):
                condition = text(ancestor.child_by_field_name('condition'), source)
                if re.search(r'c_dialect_objc|RID_AT_|C_ID_CLASSNAME', condition):
                    excluded = True
            ancestor = ancestor.parent
        if excluded:
            continue
        for argument in args.named_children:
            message = string(argument, source)
            if message is not None:
                message = gcc_template(message)
                if message and eligible(message) and not re.search(r'Objective-C|objc|@interface|@implementation', message, re.I):
                    result.append((message, node.start_point.row + 1))
                break
    return result


def clang_template(message):
    # Select/plural text is a single runtime choice, never separate invented species.
    previous = None
    while previous != message:
        previous = message
        message = re.sub(r'%(?:select|plural)\{[^{}]*\}\d+', SLOT, message)
    message = re.sub(r'%s\d+', SLOT, message)
    message = re.sub(r'%(?:ordinal)?\d+', SLOT, message)
    return None if '%' in message else clean(message)


def clang_definitions(contents, parser=False):
    result = []
    for match in re.finditer(r'\bdef\s+(\w+)\s*:\s*(Error|Fatal)\s*<\s*((?:"(?:\\.|[^"\\])*"\s*)+)', contents):
        code = match[1]
        if parser and code not in CLANG_PARSE:
            continue
        if not parser and re.search(r'cxx|objc|opencl|cuda|hlsl|module|raw_|pch|header_unit|embed', code, re.I):
            continue
        try:
            message = ''.join(ast.literal_eval(part.group()) for part in re.finditer(r'"(?:\\.|[^"\\])*"', match[3]))
        except (ValueError, SyntaxError):
            continue
        if re.search(r'C\+\+|Objective-C|raw string|module|OpenCL|CUDA|HLSL', message, re.I):
            continue
        message = clang_template(message)
        if message and eligible(message):
            result.append((code, message, contents.count('\n', 0, match.start()) + 1))
    return result


def cppcheck_calls(contents):
    source = contents.encode()
    tree = Parser(Language(tree_sitter_cpp.language())).parse(source)
    result = []
    for node in walk(tree.root_node):
        if node.type != 'call_expression' or node.has_error:
            continue
        name = text(node.child_by_field_name('function'), source)
        args = node.child_by_field_name('arguments')
        if name not in ('reportError', 'reportErr') or not args:
            continue
        children = args.named_children
        severity = next((index for index, child in enumerate(children) if text(child, source) == 'Severity::error'), None)
        if severity is None or len(children) <= severity + 2:
            continue
        code = string(children[severity + 1], source)
        # Some messages are assembled dynamically. The stable reported ID alone
        # still identifies a diagnostic; the display label comes from its function.
        message = string(children[severity + 2], source)
        function = node
        while function and function.type != 'function_definition':
            function = function.parent
        signature = text(function.child_by_field_name('declarator'), source) if function else ''
        if not code or code in ('coutCerrMisusage', 'va_start_referencePassed') or not re.fullmatch(r'[A-Za-z][\w]*', code) or CPP_ONLY.search((message or '') + ' ' + code + ' ' + signature):
            continue
        label = clean(message.split('\n')[0]) if message else code
        result.append((code, label[:160], node.start_point.row + 1))
    return result


def stream_template(node, source):
    if node.type == 'call_expression' and text(node.child_by_field_name('function'), source) in ('Err', 'ErrAlways'):
        return ''
    fixed = string(node, source)
    if fixed is not None:
        return fixed
    if node.type == 'binary_expression' and text(node.child_by_field_name('operator'), source) in ('+', '<<'):
        left = stream_template(node.child_by_field_name('left'), source)
        right = stream_template(node.child_by_field_name('right'), source)
        if left is None and right is None:
            return None
        return (left if left is not None else SLOT) + (right if right is not None else SLOT)
    return None


def linker_calls(contents):
    source = contents.encode()
    tree = Parser(Language(tree_sitter_cpp.language())).parse(source)
    result = []
    for node in walk(tree.root_node):
        message = None
        if node.type == 'expression_statement' and not node.has_error and node.named_children:
            expression = node.named_children[0]
            head = expression
            while head.type == 'binary_expression' and text(head.child_by_field_name('operator'), source) == '<<':
                head = head.child_by_field_name('left')
            if head.type == 'call_expression' and text(head.child_by_field_name('function'), source) in ('Err', 'ErrAlways'):
                message = stream_template(expression, source)
        elif node.type == 'call_expression' and not node.has_error:
            name = text(node.child_by_field_name('function'), source)
            args = node.child_by_field_name('arguments')
            if name.endswith('.error') and args and args.named_children:
                message = stream_template(args.named_children[0], source)
        if message and '\n' not in message and eligible(clean(message), 12) and not CPP_ONLY.search(message):
            result.append((clean(message), node.start_point.row + 1))
    return result


def runtime_calls(contents, asan):
    source = contents.encode()
    tree = Parser(Language(tree_sitter_cpp.language())).parse(source)
    result = []
    for node in walk(tree.root_node):
        if node.type != 'call_expression' or node.has_error:
            continue
        name = text(node.child_by_field_name('function'), source)
        args = node.child_by_field_name('arguments')
        if (asan and name != 'Report') or (not asan and name != 'Diag') or not args:
            continue
        if not asan and not any(text(arg, source) == 'DL_Error' for arg in args.named_children):
            continue
        function = node.parent
        while function and function.type != 'function_definition':
            function = function.parent
        signature = text(function.child_by_field_name('declarator'), source) if function else ''
        if re.search(r'NewDelete|AllocTypeMismatch|DynamicType|MissingReturn|Vptr|CFIBadType|ObjC', signature):
            continue
        message = next((string(arg, source) for arg in args.named_children if string(arg, source) is not None), None)
        if message is None:
            continue
        if asan:
            if not message.startswith('ERROR: AddressSanitizer: '):
                continue
            message = gcc_template(message.split('\n')[0].removeprefix('ERROR: AddressSanitizer: '))
        else:
            message = clang_template(message)
        if message and eligible(message, 16):
            result.append((message, node.start_point.row + 1))
    return result


def main():
    records, files = [], []
    def add(tool, path, line, kind, message, code=None):
        source = f'https://github.com/{REPOS[tool]}/blob/{COMMITS[tool]}/{path}#L{line}'
        key = hashlib.sha256(f'{kind}|{code if code else message.casefold()}'.encode()).hexdigest()
        records.append(dict(key=key, tool=tool, kind=kind, template=message, code=code, source=source))

    listing = json.loads(request(f'https://api.github.com/repos/{REPOS["GCC"]}/contents/gcc/c?ref={COMMITS["GCC"]}'))
    gcc_paths = [item['path'] for item in listing if item['name'].endswith('.cc')]
    clang_paths = ['clang/include/clang/Basic/DiagnosticLexKinds.td', 'clang/include/clang/Basic/DiagnosticParseKinds.td']
    cpp_paths = ['lib/' + name + '.cpp' for name in CPP_FILES]
    msvc_paths = ['docs/error-messages/compiler-errors-1/compiler-errors-c2001-through-c2099.md',
                  'docs/error-messages/compiler-errors-1/compiler-errors-c2100-through-c2199.md',
                  'docs/error-messages/compiler-errors-1/compiler-errors-c2200-through-c2299.md',
                  'docs/error-messages/compiler-errors-1/compiler-fatal-errors-c999-through-c1999.md']
    msvc_paths += ['docs/error-messages/tool-errors/linker-tools-error-lnk' + code + '.md'
                   for code in ('1104', '1107', '1112', '1120', '1123', '1127', '1158', '1168', '1181', '1189', '2001', '2005', '2019')]
    lld_paths = ['lld/ELF/' + name + '.cpp' for name in ('Driver', 'InputFiles', 'Writer', 'Relocations', 'Symbols', 'LinkerScript', 'SyntheticSections')]
    runtime_paths = ['compiler-rt/lib/asan/asan_errors.cpp', 'compiler-rt/lib/ubsan/ubsan_handlers.cpp']
    tasks = [('GCC', path) for path in gcc_paths] + [('Clang', path) for path in clang_paths + runtime_paths] + [('Cppcheck', path) for path in cpp_paths] + [('MSVC', path) for path in msvc_paths] + [('LLD', path) for path in lld_paths]
    def get(task):
        return task, fetch(*task)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for (tool, path), contents in pool.map(get, tasks):
            files.append(dict(tool=tool, path=path, sha256=hashlib.sha256(contents.encode()).hexdigest()))
            before = len(records)
            if tool == 'GCC':
                for message, line in gcc_calls(contents):
                    add(tool, path, line, 'compiler-template', message)
            elif tool == 'Clang':
                if path.startswith('compiler-rt/'):
                    asan = '/asan/' in path
                    for message, line in runtime_calls(contents, asan):
                        add(tool, path, line, 'asan-template' if asan else 'ubsan-template', message)
                else:
                    for code, message, line in clang_definitions(contents, 'ParseKinds' in path):
                        add(tool, path, line, 'compiler-template', message)
            elif tool == 'Cppcheck':
                for code, label, line in cppcheck_calls(contents):
                    add(tool, path, line, 'cppcheck-code', label, code)
            elif tool == 'LLD':
                for message, line in linker_calls(contents):
                    add(tool, path, line, 'linker-template', message)
            else:
                if '/tool-errors/' in path:
                    code = re.search(r'lnk(\d+)', path)[1]
                    label = next((line.strip().lstrip('> ').strip() for line in contents.splitlines()
                                  if line.startswith('> ')), 'Linker error LNK' + code)
                    line = next((index for index, line in enumerate(contents.splitlines(), 1) if line.startswith('> ')), 1)
                    add(tool, path, line, 'msvc-linker-code', label, 'LNK' + code)
                for match in re.finditer(r'^\|\s*(?:\[)?(?:Compiler error|Fatal error)\s+(C\d{4})[^|]*\|\s*([^\n|]+)', contents, re.M | re.I):
                    code, label = match[1], re.sub(r'<[^>]+>|\*|`', '', match[2]).strip()
                    if code in MSVC_CODES and not CPP_ONLY.search(label):
                        add(tool, path, contents.count('\n', 0, match.start()) + 1, 'msvc-code', label, code)
            print(f'{tool} {path}: {len(records) - before}', flush=True)
    unique = {}
    for record in records:
        if record['key'] not in unique:
            unique[record['key']] = record | {'sources': [record['source']], 'tools': [record['tool']]}
        else:
            unique[record['key']]['sources'].append(record['source'])
            if record['tool'] not in unique[record['key']]['tools']:
                unique[record['key']]['tools'].append(record['tool'])
    path = ROOT / 'server/c_templates.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    existing = {record['key']: record for record in old}
    for record in existing.values():
        if record['kind'] == 'ubsan-template' and re.search(r'ObjC|Objective-C', record['template'], re.I):
            record['excluded'] = 'Objective-C-only diagnostic'
    next_id = max([199999] + [record['id'] for record in old]) + 1
    for key, record in sorted(unique.items()):
        if key not in existing:
            existing[key] = record | {'id': next_id}
            next_id += 1
    path.write_text(json.dumps(list(existing.values()), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifests = []
    for tool in ('GCC', 'Clang', 'Cppcheck', 'MSVC', 'LLD'):
        license_path = {'GCC': 'COPYING3', 'Clang': 'LICENSE.TXT', 'Cppcheck': 'COPYING', 'MSVC': 'LICENSE', 'LLD': 'LICENSE.TXT'}[tool]
        notice = fetch(tool, license_path)
        dest = ROOT / 'docs/catalog-licenses' / f'C-{tool}.txt'
        dest.write_text(f'{tool}\nhttps://github.com/{REPOS[tool]}/tree/{COMMITS[tool]}\n\n{notice}', encoding='utf-8')
        manifests.append(dict(tool=tool, repository=REPOS[tool], commit=COMMITS[tool],
                              definitions=sum(tool in r['tools'] for r in unique.values()), files=[f for f in files if f['tool'] == tool],
                              license=str(dest.relative_to(ROOT)).replace('\\', '/')))
    (ROOT / 'docs/c-catalog-sources.json').write_text(json.dumps(manifests, indent=2) + '\n', encoding='utf-8')
    print(f'{len(existing)} distinct C diagnostic records')


if __name__ == '__main__':
    main()
