"""Extract diagnostic templates from real Python raise statements, never execute sources.

Downloads are an explicit maintenance step. Normal builds use the committed snapshot.
Only stable literal/f-string/format templates with enough fixed text are accepted.
Tests, examples, warnings, dynamic exception constructors and inferred causes are excluded.
"""
import ast
import builtins
import hashlib
import io
import json
import re
import string
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server.catalog import mask

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ('numpy', 'numpy/numpy', 'numpy'),
    ('pandas', 'pandas-dev/pandas', 'pandas'),
    ('scipy', 'scipy/scipy', 'scipy'),
    ('scikit-learn', 'scikit-learn/scikit-learn', 'sklearn'),
    ('sympy', 'sympy/sympy', 'sympy'),
    ('Django', 'django/django', 'django'),
    ('SQLAlchemy', 'sqlalchemy/sqlalchemy', 'lib/sqlalchemy'),
    ('Flask', 'pallets/flask', 'src/flask'),
    ('requests', 'psf/requests', 'src/requests'),
    ('FastAPI', 'fastapi/fastapi', 'fastapi'),
]
BUILTIN_ERRORS = {name for name in dir(builtins) if isinstance(getattr(builtins, name), type)
                  and issubclass(getattr(builtins, name), Exception)
                  and not issubclass(getattr(builtins, name), Warning)
                  and name not in {'StopIteration', 'StopAsyncIteration', 'ExceptionGroup', 'KeyError'}}
SLOT = '\x00'


def template(node, values):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.JoinedStr):
        return ''.join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else SLOT for v in node.values)
    if isinstance(node, ast.BinOp):
        left = template(node.left, values)
        if left is None:
            return None
        if isinstance(node.op, ast.Add):
            right = template(node.right, values)
            return left + right if right is not None else None
        if isinstance(node.op, ast.Mod):
            value = left.replace('%%', '\x01')
            value = re.sub(r'%(?:\([^)]+\))?[#0 +\-]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[diouxXeEfFgGcrsa]', SLOT, value)
            return None if '%' in value else value.replace('\x01', '%')
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'format':
        value = template(node.func.value, values)
        if value is not None:
            try:
                return ''.join(literal + (SLOT if field is not None else '')
                               for literal, field, _, _ in string.Formatter().parse(value))
            except ValueError:
                return None
    return None


class Raises(ast.NodeVisitor):
    def __init__(self):
        self.values = {}
        self.imports = {}
        self.items = []

    def generic_visit(self, node):
        # Expressions cannot contain raise statements; avoid descending into
        # generated symbolic expressions thousands of nodes deep.
        if not isinstance(node, ast.expr):
            super().generic_visit(node)

    def visit_ClassDef(self, node):
        old = self.values.copy()
        for statement in node.body:
            self.visit(statement)
        self.values = old

    def visit_ImportFrom(self, node):
        for item in node.names:
            self.imports[item.asname or item.name] = f'{node.module}.{item.name}'

    def visit_Assign(self, node):
        try:
            value = template(node.value, self.values)
        except RecursionError:
            value = None
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.values[target.id] = value

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Name):
            self.values[node.target.id] = None

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Name):
            self.values[node.target.id] = template(node.value, self.values) if node.value else None

    def visit_Delete(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.values[target.id] = None

    def visit_If(self, node):
        before = self.values.copy()
        for statement in node.body:
            self.visit(statement)
        yes = self.values.copy()
        self.values = before.copy()
        for statement in node.orelse:
            self.visit(statement)
        no = self.values.copy()
        self.values = {key: value if no.get(key) == value else None for key, value in yes.items()}

    def visit_For(self, node):
        before = self.values.copy()
        for child in ast.walk(node.target):
            if isinstance(child, ast.Name):
                self.values[child.id] = None
        for statement in node.body:
            self.visit(statement)
        after = self.values.copy()
        self.values = {key: value if after.get(key) == value else None for key, value in before.items()}
        for statement in node.orelse:
            self.visit(statement)

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        before = self.values.copy()
        for statement in node.body:
            self.visit(statement)
        after = self.values.copy()
        self.values = {key: value if after.get(key) == value else None for key, value in before.items()}
        for statement in node.orelse:
            self.visit(statement)

    def visit_Try(self, node):
        before = self.values.copy()
        for statement in node.body:
            self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)
        outcomes = [self.values.copy()]
        for handler in node.handlers:
            self.values = before.copy()
            for statement in handler.body:
                self.visit(statement)
            outcomes.append(self.values.copy())
        self.values = {key: value if all(other.get(key) == value for other in outcomes) else None for key, value in before.items()}
        for statement in node.finalbody:
            self.visit(statement)

    visit_TryStar = visit_Try

    def visit_FunctionDef(self, node):
        old = self.values.copy()
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            self.values[arg.arg] = None
        for arg in (node.args.vararg, node.args.kwarg):
            if arg:
                self.values[arg.arg] = None
        for statement in node.body:
            self.visit(statement)
        self.values = old

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Raise(self, node):
        call = node.exc
        if not isinstance(call, ast.Call) or len(call.args) != 1 or call.keywords:
            return
        if not isinstance(call.func, ast.Name):
            return
        name = ast.unparse(call.func)
        simple = name.rsplit('.', 1)[-1]
        if simple not in BUILTIN_ERRORS:
            # Imported custom exceptions can override __str__, so do not infer their output.
            return
        if simple in self.imports or simple in self.values:
            return
        message = template(call.args[0], self.values)
        if message is None:
            return
        message = message.strip()
        parts = message.split(SLOT)
        fixed = ''.join(parts)
        if len(fixed) < 20 or max(map(len, parts), default=0) < 12 or len(message) > 500:
            return
        # IOError/EnvironmentError are aliases: Python prints OSError.
        runtime_name = getattr(builtins, simple).__name__
        self.items.append((runtime_name, message, node.lineno))


def request(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Bug-Index-catalog/0.3'}), timeout=120) as response:
        return response.read()


def download(source):
    package, repo, prefix = source
    cache = ROOT / 'artifacts' / 'catalog-sources'
    cache.mkdir(parents=True, exist_ok=True)
    meta_path = cache / f'{package}.json'
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    else:
        meta = json.loads(request(f'https://api.github.com/repos/{repo}/commits/HEAD'))
        meta_path.write_text(json.dumps({'sha': meta['sha']}))
    sha = meta['sha']
    path = cache / f'{package}-{sha}.tar.gz'
    if not path.exists():
        path.write_bytes(request(f'https://codeload.github.com/{repo}/tar.gz/{sha}'))
    return source, sha, path.read_bytes()


def extract(source, sha, data):
    package, repo, prefix = source
    result = []
    licenses = []
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            if not member.isfile():
                continue
            relative = member.name.split('/', 1)[-1]
            if '/' not in relative and re.match(r'(?:LICENSE|COPYING)', relative, re.I):
                licenses.append((relative, archive.extractfile(member).read().decode('utf-8', errors='replace')))
            if not relative.startswith(prefix + '/') or not relative.endswith('.py'):
                continue
            if any(part in {'tests', 'test', 'testing', 'examples', 'benchmarks', 'conftest.py'} or part.startswith('test_') for part in relative.split('/')):
                continue
            try:
                tree = ast.parse(archive.extractfile(member).read().decode('utf-8'))
            except (UnicodeError, SyntaxError):
                continue
            visitor = Raises()
            visitor.visit(tree)
            for exception, message, line in visitor.items:
                # Whitespace differences cannot create additional species.
                canonical = re.sub(r'\s+', ' ', re.sub(SLOT + '+', SLOT, message))
                example = canonical.replace(SLOT, 'sample_value')
                try:
                    error = getattr(builtins, exception)(example)
                except TypeError:
                    continue
                if str(error) != example or type(error).__name__ != exception:
                    continue
                if mask(example) != example:
                    continue  # A masked literal cannot be reliably recognized.
                key = hashlib.sha256(f'{package}|{exception}|{canonical.casefold()}'.encode()).hexdigest()
                result.append(dict(key=key, package=package, exception=exception, template=canonical,
                                   module=prefix.split('/')[-1], path=relative,
                                   source=f'https://github.com/{repo}/blob/{sha}/{relative}#L{line}'))
    notice = ROOT / 'docs' / 'catalog-licenses' / f'{package}.txt'
    notice.parent.mkdir(parents=True, exist_ok=True)
    notice.write_text(f'{package}\nhttps://github.com/{repo}/tree/{sha}\n\n' + '\n\n'.join(name + '\n' + body for name, body in licenses), encoding='utf-8')
    return result, dict(package=package, repository=repo, commit=sha,
                        archive_sha256=hashlib.sha256(data).hexdigest(), license=str(notice.relative_to(ROOT)).replace('\\', '/'))


def main():
    path = ROOT / 'server' / 'library_templates.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    existing = {entry['key']: entry for entry in old}
    next_id = max([999] + [e['id'] for e in old]) + 1
    manifest = []
    validated = set()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for source, sha, data in pool.map(download, SOURCES):
            entries, meta = extract(source, sha, data)
            unique = {entry['key']: entry for entry in entries}
            validated.update(unique)
            for key in sorted(unique):
                if key not in existing:
                    existing[key] = unique[key] | {'id': next_id}
                    next_id += 1
            meta['templates'] = len(unique)
            manifest.append(meta)
            print(f"{source[0]}: {len(unique)} unique source templates", flush=True)
    # Keep already-published source templates even if a later upstream version
    # removes that raise statement. Old library versions still emit the error.
    path.write_text(json.dumps(sorted(existing.values(), key=lambda e: e['id']), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'docs' / 'catalog-sources.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'{len(existing)} templates committed to snapshot')


if __name__ == '__main__':
    main()
