"""Source-backed Java/Android diagnostic import. Never executes upstream code.

Tree-sitter identifies actual throw/new expressions. The supported subset uses
standard JVM exception constructors and statically readable message templates.
Tests, examples, dynamic message factories and custom exception rendering are
excluded instead of inventing their output. Published IDs remain append-only.
"""
import hashlib
import json
import re
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_java

from scripts.import_library_catalog import download, request
from server.catalog import mask

ROOT = Path(__file__).resolve().parent.parent
SLOT = '\x00'
SOURCES = [
    ('OpenJDK', 'openjdk/jdk', 'src'),
    ('Android', 'aosp-mirror/platform_frameworks_base', ''),
    ('Spring', 'spring-projects/spring-framework', ''),
    ('Spring Boot', 'spring-projects/spring-boot', ''),
    ('Gradle', 'gradle/gradle', ''),
    ('Maven', 'apache/maven', ''),
    ('Hibernate', 'hibernate/hibernate-orm', ''),
    ('Netty', 'netty/netty', ''),
    ('Jackson', 'FasterXML/jackson-databind', ''),
    ('Guava', 'google/guava', 'guava/src'),
]
ORIGINS = {
    'OpenJDK': ['java.', 'javax.', 'jdk.', 'sun.', 'com.sun.'],
    'Android': ['android.', 'com.android.', 'dalvik.'],
    'Spring': ['org.springframework.'],
    'Spring Boot': ['org.springframework.boot.'],
    'Gradle': ['org.gradle.'],
    'Maven': ['org.apache.maven.'],
    'Hibernate': ['org.hibernate.'],
    'Netty': ['io.netty.'],
    'Jackson': ['com.fasterxml.jackson.'],
    'Guava': ['com.google.common.'],
}

# String constructors with the standard Throwable getMessage/toString behavior.
# Custom types are admitted only after their constructors are separately audited.
STANDARD = {
    'IllegalArgumentException': 'java.lang.IllegalArgumentException',
    'IllegalStateException': 'java.lang.IllegalStateException',
    'UnsupportedOperationException': 'java.lang.UnsupportedOperationException',
    'NullPointerException': 'java.lang.NullPointerException',
    'IndexOutOfBoundsException': 'java.lang.IndexOutOfBoundsException',
    'ArrayIndexOutOfBoundsException': 'java.lang.ArrayIndexOutOfBoundsException',
    'StringIndexOutOfBoundsException': 'java.lang.StringIndexOutOfBoundsException',
    'NumberFormatException': 'java.lang.NumberFormatException',
    'ArithmeticException': 'java.lang.ArithmeticException',
    'ClassCastException': 'java.lang.ClassCastException',
    'SecurityException': 'java.lang.SecurityException',
    'RuntimeException': 'java.lang.RuntimeException',
    'Exception': 'java.lang.Exception',
    'AssertionError': 'java.lang.AssertionError',
    'IOException': 'java.io.IOException',
    'EOFException': 'java.io.EOFException',
    'FileNotFoundException': 'java.io.FileNotFoundException',
    'InterruptedIOException': 'java.io.InterruptedIOException',
    'MalformedURLException': 'java.net.MalformedURLException',
    'ProtocolException': 'java.net.ProtocolException',
    'SocketException': 'java.net.SocketException',
    'SocketTimeoutException': 'java.net.SocketTimeoutException',
    'ConnectException': 'java.net.ConnectException',
    'UnknownHostException': 'java.net.UnknownHostException',
    'SQLException': 'java.sql.SQLException',
    'SQLFeatureNotSupportedException': 'java.sql.SQLFeatureNotSupportedException',
    'SQLDataException': 'java.sql.SQLDataException',
    'SQLIntegrityConstraintViolationException': 'java.sql.SQLIntegrityConstraintViolationException',
    'SQLSyntaxErrorException': 'java.sql.SQLSyntaxErrorException',
    'NoSuchElementException': 'java.util.NoSuchElementException',
    'ConcurrentModificationException': 'java.util.ConcurrentModificationException',
    'InputMismatchException': 'java.util.InputMismatchException',
    'MissingResourceException': 'java.util.MissingResourceException',
    'DateTimeException': 'java.time.DateTimeException',
    'DateTimeParseException': 'java.time.format.DateTimeParseException',
    'IllegalFormatException': 'java.util.IllegalFormatException',
    'CharacterCodingException': 'java.nio.charset.CharacterCodingException',
    'UnsupportedCharsetException': 'java.nio.charset.UnsupportedCharsetException',
    'UnsupportedEncodingException': 'java.io.UnsupportedEncodingException',
    'InvalidObjectException': 'java.io.InvalidObjectException',
    'NotSerializableException': 'java.io.NotSerializableException',
    'StreamCorruptedException': 'java.io.StreamCorruptedException',
    'ClassNotFoundException': 'java.lang.ClassNotFoundException',
    'NoSuchMethodException': 'java.lang.NoSuchMethodException',
    'NoSuchFieldException': 'java.lang.NoSuchFieldException',
    'IllegalAccessException': 'java.lang.IllegalAccessException',
    'InstantiationException': 'java.lang.InstantiationException',
    'InterruptedException': 'java.lang.InterruptedException',
    'ReflectiveOperationException': 'java.lang.ReflectiveOperationException',
    'CloneNotSupportedException': 'java.lang.CloneNotSupportedException',
    'TimeoutException': 'java.util.concurrent.TimeoutException',
    'RejectedExecutionException': 'java.util.concurrent.RejectedExecutionException',
    'CancellationException': 'java.util.concurrent.CancellationException',
    'ExecutionException': 'java.util.concurrent.ExecutionException',
    'InvalidKeyException': 'java.security.InvalidKeyException',
    'NoSuchAlgorithmException': 'java.security.NoSuchAlgorithmException',
    'InvalidAlgorithmParameterException': 'java.security.InvalidAlgorithmParameterException',
    'InvalidKeySpecException': 'java.security.spec.InvalidKeySpecException',
    'SignatureException': 'java.security.SignatureException',
    'KeyStoreException': 'java.security.KeyStoreException',
    'CertificateException': 'java.security.cert.CertificateException',
    'CertificateEncodingException': 'java.security.cert.CertificateEncodingException',
    'CertificateParsingException': 'java.security.cert.CertificateParsingException',
    'CertificateExpiredException': 'java.security.cert.CertificateExpiredException',
    'CertificateNotYetValidException': 'java.security.cert.CertificateNotYetValidException',
    'SSLException': 'javax.net.ssl.SSLException',
    'SSLHandshakeException': 'javax.net.ssl.SSLHandshakeException',
    'SSLProtocolException': 'javax.net.ssl.SSLProtocolException',
    'SSLPeerUnverifiedException': 'javax.net.ssl.SSLPeerUnverifiedException',
    'BadPaddingException': 'javax.crypto.BadPaddingException',
    'IllegalBlockSizeException': 'javax.crypto.IllegalBlockSizeException',
    'ShortBufferException': 'javax.crypto.ShortBufferException',
    'NamingException': 'javax.naming.NamingException',
    'NamingSecurityException': 'javax.naming.NamingSecurityException',
    'NameNotFoundException': 'javax.naming.NameNotFoundException',
    'InvalidNameException': 'javax.naming.InvalidNameException',
    'GeneralSecurityException': 'java.security.GeneralSecurityException',
    'AccessControlException': 'java.security.AccessControlException',
    'InternalError': 'java.lang.InternalError',
    'LinkageError': 'java.lang.LinkageError',
    'UnsatisfiedLinkError': 'java.lang.UnsatisfiedLinkError',
    'OutOfMemoryError': 'java.lang.OutOfMemoryError',
    'StackOverflowError': 'java.lang.StackOverflowError',
}
# Constructors here either require additional arguments or render a value rather
# than a diagnostic. Do not assume that a string alone has the desired meaning.
UNSAFE = {'MissingResourceException', 'DateTimeParseException', 'IllegalFormatException',
          'CharacterCodingException', 'UnsupportedCharsetException', 'ExecutionException'}
STANDARD = {key: value for key, value in STANDARD.items() if key not in UNSAFE}
HELPERS = {
    'org.springframework.util.Assert': {
        'notNull': 'java.lang.IllegalArgumentException', 'isTrue': 'java.lang.IllegalArgumentException',
        'hasLength': 'java.lang.IllegalArgumentException', 'hasText': 'java.lang.IllegalArgumentException',
        'notEmpty': 'java.lang.IllegalArgumentException', 'noNullElements': 'java.lang.IllegalArgumentException',
        'state': 'java.lang.IllegalStateException',
    },
    'java.util.Objects': {'requireNonNull': 'java.lang.NullPointerException'},
    'com.google.common.base.Preconditions': {
        'checkArgument': 'java.lang.IllegalArgumentException', 'checkState': 'java.lang.IllegalStateException',
        'checkNotNull': 'java.lang.NullPointerException',
    },
}


def walk(node):
    todo = [node]
    while todo:
        current = todo.pop()
        yield current
        todo.extend(reversed(current.named_children))


def text(node, source):
    return source[node.start_byte:node.end_byte].decode('utf-8') if node else ''


def literal(value):
    # Java's ordinary quoted strings (not text blocks). Decode known escapes only.
    if not value.startswith('"') or value.startswith('"""') or not value.endswith('"'):
        return None
    body = value[1:-1]
    escapes = {'b': '\b', 't': '\t', 'n': '\n', 'f': '\f', 'r': '\r', '"': '"', "'": "'", '\\': '\\', 's': ' '}
    output, index = [], 0
    while index < len(body):
        if body[index] != '\\':
            output.append(body[index]); index += 1; continue
        index += 1
        if index >= len(body):
            return None
        if body[index] in escapes:
            output.append(escapes[body[index]]); index += 1
        elif body[index] == 'u':
            # Unicode escapes are translated before Java tokenization; tricky
            # quote/control escapes are rejected instead of guessing semantics.
            return None
        elif body[index] in '01234567':
            end = index + 1
            limit = 3 if body[index] in '0123' else 2
            while end < len(body) and end - index < limit and body[end] in '01234567':
                end += 1
            output.append(chr(int(body[index:end], 8))); index = end
        else:
            return None
    return ''.join(output)


def template(node, source):
    if node.type == 'string_literal':
        return literal(text(node, source))
    if node.type == 'parenthesized_expression':
        return template(node.named_children[0], source)
    if node.type == 'binary_expression':
        operator = text(node.child_by_field_name('operator'), source)
        if operator != '+':
            return None
        left = template(node.child_by_field_name('left'), source)
        right = template(node.child_by_field_name('right'), source)
        # At least one part must prove this is string concatenation. An unreadable
        # expression can be a runtime value only after the fixed text is known.
        if left is None and right is None:
            return None
        return (left if left is not None else SLOT) + (right if right is not None else SLOT)
    if node.type == 'method_invocation':
        obj = text(node.child_by_field_name('object'), source)
        name = text(node.child_by_field_name('name'), source)
        args = node.child_by_field_name('arguments')
        if obj not in ('String', 'java.lang.String') or name != 'format' or not args or not args.named_children:
            return None
        fmt = template(args.named_children[0], source)
        if fmt is None or SLOT in fmt:
            return None
        # Formatter uses %% and %n as literals, and indexed/flagged fields as values.
        fmt = fmt.replace('%%', '\x01').replace('%n', '\n')
        fmt = re.sub(r'%(?:\d+\$)?[-#+ 0,(<]*\d*(?:\.\d+)?(?:[tT][A-Za-z]|[bBhHsScCdoxXeEfgGaA])', SLOT, fmt)
        return None if '%' in fmt else fmt.replace('\x01', '%')
    return None


def throws(source, strict=False):
    parser = Parser(Language(tree_sitter_java.language()))
    tree = parser.parse(source)
    if tree.root_node.has_error:
        if strict:
            raise ValueError('Java grammar could not parse this source')
        return []
    package_node = next((node for node in tree.root_node.named_children if node.type == 'package_declaration'), None)
    module = re.sub(r'^package\s+|;$', '', text(package_node, source)).strip()
    imports = {}
    static_imports = {}
    wildcards = []
    for node in tree.root_node.named_children:
        if node.type == 'import_declaration':
            name = re.sub(r'^import\s+|;$', '', text(node, source)).strip()
            if name.startswith('static '):
                name = name[7:]
                static_imports[name.rsplit('.', 1)[-1]] = name.rsplit('.', 1)[0]
                continue
            if name.endswith('.*'):
                wildcards.append(name[:-2])
            else:
                imports[name.rsplit('.', 1)[-1]] = name
    declared = {text(node.child_by_field_name('name'), source) for node in walk(tree.root_node)
                if node.type in ('class_declaration', 'interface_declaration', 'enum_declaration', 'record_declaration')}
    result = []
    for node in walk(tree.root_node):
        if node.type == 'method_invocation':
            name = text(node.child_by_field_name('name'), source)
            obj = text(node.child_by_field_name('object'), source)
            owner = imports.get(obj, obj) if obj else static_imports.get(name, static_imports.get('*'))
            qualified = HELPERS.get(owner, {}).get(name)
            args = node.child_by_field_name('arguments')
            if qualified and args and len(args.named_children) == 2:
                message = template(args.named_children[1], source)
                if message is not None:
                    message = re.sub(SLOT + '+', SLOT, re.sub(r'\s+', ' ', message)).strip()
                    parts = message.split(SLOT)
                    if len(''.join(parts)) >= 20 and max(map(len, parts), default=0) >= 12 and len(message) <= 500 and module:
                        if mask(message.replace(SLOT, 'sample_value')) == message.replace(SLOT, 'sample_value'):
                            result.append(dict(exception=qualified, template=message, module=module,
                                               line=node.start_point.row + 1, kind='precondition-call'))
            continue
        if node.type != 'throw_statement' or not node.named_children:
            continue
        creation = node.named_children[0]
        if creation.type != 'object_creation_expression':
            continue
        type_name = text(creation.child_by_field_name('type'), source)
        simple = type_name.rsplit('.', 1)[-1]
        qualified = STANDARD.get(simple)
        if not qualified or simple in declared:
            continue
        # Resolve imports; don't treat a project-defined IOException as java.io.IOException.
        if '.' in type_name:
            if type_name != qualified:
                continue
        elif simple in imports:
            if imports[simple] != qualified:
                continue
        elif not (qualified.startswith('java.lang.') or module == qualified.rsplit('.', 1)[0]
                  or qualified.rsplit('.', 1)[0] in wildcards):
            continue
        args = creation.child_by_field_name('arguments')
        if not args or len(args.named_children) != 1:
            continue
        message = template(args.named_children[0], source)
        if message is None:
            continue
        message = re.sub(SLOT + '+', SLOT, re.sub(r'\s+', ' ', message)).strip()
        parts = message.split(SLOT)
        if len(''.join(parts)) < 20 or max(map(len, parts), default=0) < 12 or len(message) > 500:
            continue
        if mask(message.replace(SLOT, 'sample_value')) != message.replace(SLOT, 'sample_value'):
            continue
        if not module:
            continue
        result.append(dict(exception=qualified, template=message, module=module,
                           line=node.start_point.row + 1))
    return result


def extract(source, sha, data):
    package, repo, prefix = source
    result, licenses = {}, []
    skipped_files, parsed_files = 0, 0
    # Read data only. No archive paths are ever extracted onto the filesystem.
    import io
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            if not member.isfile():
                continue
            path = member.name.split('/', 1)[-1]
            if '/' not in path and re.match(r'(?:LICENSE|COPYING|NOTICE|ASSEMBLY_EXCEPTION)', path, re.I):
                licenses.append((path, archive.extractfile(member).read().decode('utf-8', errors='replace')))
            if not path.endswith('.java') or (prefix and not path.startswith(prefix + '/')):
                continue
            if any(part.lower() in {'test', 'tests', 'testfixtures', 'testing', 'examples', 'samples', 'benchmarks', 'jmh', 'testframework', 'integrationtest'}
                   or part.lower().endswith('tests') for part in path.split('/')):
                continue
            if package not in ('OpenJDK', 'Android', 'Guava') and '/src/main/java/' not in '/' + path:
                continue
            contents = archive.extractfile(member).read()
            if b'throw ' not in contents and not any(value in contents for value in (b'Assert.', b'Preconditions.', b'requireNonNull', b'checkArgument', b'checkState')):
                continue
            parsed_files += 1
            try:
                items = throws(contents, strict=True)
            except (UnicodeError, RecursionError, ValueError):
                skipped_files += 1
                continue
            for item in items:
                if not item['module'].startswith(tuple(ORIGINS[package])):
                    continue
                # Same exception/message inside the same library is one species,
                # independent of which files throw it or which values are supplied.
                key = hashlib.sha256(f'{package}|{item["exception"]}|{item["template"].casefold()}'.encode()).hexdigest()
                if key not in result:
                    result[key] = dict(key=key, package=package, exception=item['exception'], template=item['template'],
                                       module=item['module'], path=path,
                                       origin_prefixes=ORIGINS[package],
                                       kind=item.get('kind', 'throw-statement'),
                                       source=f'https://github.com/{repo}/blob/{sha}/{path}#L{item["line"]}')
    notice = ROOT / 'docs/catalog-licenses' / f'{package}.txt'
    notice.parent.mkdir(parents=True, exist_ok=True)
    notice.write_text(f'{package}\nhttps://github.com/{repo}/tree/{sha}\n\n' + '\n\n'.join(name + '\n' + body for name, body in licenses), encoding='utf-8')
    return list(result.values()), dict(package=package, repository=repo, commit=sha,
                                       scope=['core/java', 'graphics/java', 'media/java', 'telephony/java'] if package == 'Android' else [prefix or 'src/main/java'],
                                       archive_sha256=hashlib.sha256(data).hexdigest(),
                                       license=str(notice.relative_to(ROOT)).replace('\\', '/'),
                                       templates=len(result), parsed_files=parsed_files, skipped_files=skipped_files)


def download_java(source):
    if source[0] != 'Android':
        return download(source)
    import io
    cache = ROOT / 'artifacts/catalog-sources'
    cache.mkdir(parents=True, exist_ok=True)
    meta_path = cache / 'Android.json'
    if not meta_path.exists():
        meta = json.loads(request(f'https://api.github.com/repos/{source[1]}/commits/HEAD'))
        meta_path.write_text(json.dumps({'sha': meta['sha']}))
    sha = json.loads(meta_path.read_text())['sha']
    path = cache / f'Android-{sha}-java-subsets.tar.gz'
    if not path.exists():
        pending = path.with_suffix('.pending')
        with tarfile.open(pending, 'w:gz') as target:
            for directory in ('core/java', 'graphics/java', 'media/java', 'telephony/java'):
                data = request(f'https://android.googlesource.com/platform/frameworks/base/+archive/{sha}/{directory}.tar.gz')
                with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
                    for member in archive:
                        if member.isfile():
                            body = archive.extractfile(member).read()
                            info = tarfile.TarInfo(f'android/{directory}/{member.name}')
                            info.size = len(body)
                            target.addfile(info, io.BytesIO(body))
            body = request(f'https://raw.githubusercontent.com/{source[1]}/{sha}/NOTICE')
            info = tarfile.TarInfo('android/NOTICE')
            info.size = len(body)
            target.addfile(info, io.BytesIO(body))
        pending.replace(path)
    return source, sha, path.read_bytes()


def main():
    path = ROOT / 'server/java_templates.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    existing = {entry['key']: entry for entry in old}
    next_id = max([99999] + [entry['id'] for entry in old]) + 1
    manifest = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for source, sha, data in pool.map(download_java, SOURCES):
            entries, meta = extract(source, sha, data)
            for entry in sorted(entries, key=lambda entry: entry['key']):
                if entry['key'] not in existing:
                    existing[entry['key']] = entry | {'id': next_id}
                    next_id += 1
            manifest.append(meta)
            print(f'{source[0]}: {len(entries)} unique verified-source templates', flush=True)
    path.write_text(json.dumps(sorted(existing.values(), key=lambda entry: entry['id']), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'docs/java-catalog-sources.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    base_path = ROOT / 'server/java_families.json'
    from server.catalog import CATALOG
    bases = json.loads(base_path.read_text(encoding='utf-8')) if base_path.exists() else []
    base_ids = {entry['exception']: entry['id'] for entry in bases}
    next_base = max([59999] + list(base_ids.values())) + 1
    current = {entry['name'].rsplit('.', 1)[-1]: entry['id'] for entry in CATALOG
               if entry['language'] == 'Java' and entry['family_id'] == entry['id'] and not entry.get('package')}
    for exception in sorted({entry['exception'] for entry in existing.values()}):
        if exception in base_ids:
            continue
        number = current.get(exception.rsplit('.', 1)[-1])
        if number is None:
            number = next_base
            next_base += 1
        base_ids[exception] = number
        bases.append(dict(exception=exception, id=number))
    base_path.write_text(json.dumps(bases, indent=2) + '\n', encoding='utf-8')
    print(f'{len(existing)} Java/Android templates in snapshot')


if __name__ == '__main__':
    main()
