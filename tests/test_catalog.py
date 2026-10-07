import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from server.catalog import CATALOG, classify, diagnostic, template_matches
from server.db import connect, initialize


@pytest.mark.parametrize('entry', CATALOG, ids=lambda e: f"{e['language']}-{e['name']}")
def test_specific_fixture_beats_generic_fallback(entry):
    result = classify(entry['sample'])
    assert result is not None
    assert result['id'] == entry['id'], (entry['name'], result['name'])
    assert result['family_id'] == entry['family_id']


@pytest.mark.parametrize('normal', [
    'Build succeeded. 0 errors.', 'User pressed Ctrl+C\nKeyboardInterrupt',
    'SystemExit: 0', 'StopIteration', 'UserWarning: a warning',
    'The documentation mentions NullPointerException and TypeError.',
    '    raise TypeError("object is not callable")',
    'const char *text = "main.c:2: error: expected semicolon";',
    'main.c:2: warning: implicit declaration of function run',
])
def test_normal_output_warnings_and_source_are_not_bugs(normal):
    assert classify(normal) is None


def test_final_chained_exception_and_windows_line_endings():
    log = 'TypeError: unsupported operand type(s) for +: int and str\r\n\r\nDuring handling of the above exception, another exception occurred:\r\n\r\nTraceback (most recent call last):\r\n  File "main.py", line 2, in run\r\nValueError: invalid literal for int() with base 10: abc\r\n'
    assert classify(log)['name'] == 'ValueError.InvalidInteger'
    assert classify('Exception in thread "main" java.lang.StackOverflowError\r\n')['id'] == 5


def test_final_unknown_cause_is_not_replaced_with_an_earlier_known_exception():
    log = 'Traceback (most recent call last):\n  File "main.py", line 1, in run\nValueError: bad input\n\nDuring handling of the above exception, another exception occurred:\n\nTraceback (most recent call last):\n  File "main.py", line 3, in run\nCustomProjectError: final failure'
    assert classify(log) is None
    assert diagnostic(log)['diagnostic'] == 'CustomProjectError: final failure'


def test_source_templates_require_library_context_and_keep_dynamic_values_out_of_species():
    entry = next(e for e in CATALOG if e.get('message_template') and '\x00' in e['message_template'])
    sample = entry['sample'].replace('sample_value', 'another_value')
    assert classify(sample)['id'] == entry['id']
    windows = sample.replace('/venv/site-packages/', 'C:\\venv\\Lib\\site-packages\\').replace(f'{entry["package"]}/', f'{entry["package"]}\\')
    # Module names can differ from display package names (sklearn/scikit-learn).
    assert classify(windows)['id'] == entry['id']
    bare = sample.split('\n')[-1]
    assert classify(bare)['id'] == entry['family_id']


def test_template_matching_handles_large_values_without_regex_backtracking():
    assert template_matches('Expected \x00 columns, got \x00', 'Expected 12 columns, got 8')
    assert not template_matches('Expected \x00 columns, got \x00', 'Expected 12 rows, got 8')
    assert template_matches('prefix \x00 x \x00 x \x00 suffix', 'prefix ' + 'x ' * 16000 + 'suffix')


def test_catalog_size_provenance_and_unique_stable_ids():
    assert len(CATALOG) >= 5000
    assert len({e['id'] for e in CATALOG}) == len(CATALOG)
    keys = [e['template_key'] for e in CATALOG if e.get('template_key')]
    assert len(set(keys)) == len(keys)
    for entry in CATALOG:
        if entry.get('verification') == 'source-template':
            assert '/blob/' in entry['source'] and '#L' in entry['source']
            assert len(entry['source'].split('/blob/')[1].split('/')[0]) == 40


def test_legacy_database_keeps_existing_records(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.sqlite3'
    monkeypatch.setenv('BUG_INDEX_DB', str(path))
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE users(id INTEGER PRIMARY KEY,github_id TEXT UNIQUE NOT NULL,
        login TEXT NOT NULL,pro INTEGER NOT NULL DEFAULT 0,ranking_opt_in INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE bugs(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
        species INTEGER NOT NULL,fingerprint TEXT NOT NULL,project TEXT NOT NULL,first_seen REAL NOT NULL,
        last_seen REAL NOT NULL,cause TEXT NOT NULL DEFAULT '',solution TEXT NOT NULL DEFAULT '',
        memo TEXT NOT NULL DEFAULT '',solved_at REAL,UNIQUE(user_id,fingerprint));
        INSERT INTO users(id,github_id,login) VALUES(1,'legacy','hunter');
        INSERT INTO bugs VALUES(7,1,9,'original-fingerprint','project',1,2,'cause','solution','memo',3);''')
    initialize()
    initialize()  # Migration is idempotent.
    with connect() as db:
        row = dict(db.execute('SELECT * FROM bugs WHERE id=7').fetchone())
    assert row['family_id'] == row['species'] == 9
    assert row['fingerprint'] == 'original-fingerprint'
    assert (row['cause'], row['solution'], row['memo'], row['solved_at']) == ('cause', 'solution', 'memo', 3)


REAL_PYTHON = [
    ('1 + "a"', 'TypeError.UnsupportedOperand'), ('value = 1; value()', 'TypeError.NotCallable'),
    ('None[0]', 'TypeError.NotSubscriptable'), ('iter(1)', 'TypeError.NotIterable'),
    ('{[]: 1}', 'TypeError.Unhashable'), ('len(1)', 'TypeError.NoLength'),
    ('x = (1,); x[0] = 2', 'TypeError.ImmutableAssignment'),
    ('[1]["x"]', 'TypeError.InvalidIndexType'), ('"x" + 1', 'TypeError.StringConcatenation'),
    ('missing_variable', 'NameError.UndefinedName'), ('[][0]', 'IndexError.ListIndex'),
    ('""[0]', 'IndexError.StringIndex'), ('()[0]', 'IndexError.TupleIndex'),
    ('[].pop()', 'IndexError.EmptyPop'), ('1 / 0', 'ZeroDivisionError.Division'),
    ('1 // 0', 'ZeroDivisionError.IntegerDivision'), ('1.0 % 0', 'ZeroDivisionError.Modulo'),
    ('int("abc")', 'ValueError.InvalidInteger'), ('float("abc")', 'ValueError.InvalidFloat'),
    ('a,b = [1,2,3]', 'ValueError.TooManyUnpack'), ('a,b = [1]', 'ValueError.TooFewUnpack'),
    ('[].remove(1)', 'ValueError.MissingListValue'), ('import math; math.sqrt(-1)', 'ValueError.MathDomain'),
    ('None.name', 'AttributeError.MissingAttribute'), ('open("definitely-missing-file-773c")', 'FileNotFoundError'),
    ('assert False', 'AssertionError'), ('if True\n pass', 'SyntaxError.MissingColon'),
    ('x = (', 'SyntaxError.UnclosedDelimiter'), ('x = "abc', 'SyntaxError.UnterminatedString'),
    ('return 1', 'SyntaxError.ReturnOutsideFunction'), ('break', 'SyntaxError.BreakOutsideLoop'),
    ('continue', 'SyntaxError.ContinueOutsideLoop'), ('if True:\npass', 'IndentationError.ExpectedBlock'),
]


@pytest.mark.parametrize('program,expected', REAL_PYTHON)
def test_real_python_errors(program, expected):
    result = subprocess.run([sys.executable, '-c', program], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    identified = classify(result.stderr)
    assert identified and identified['name'] == expected, result.stderr


REAL_JAVA = [
    ('public class Main { public static void main(String[] args) { int x = 1 } }', 'JavaCompileError.MissingSemicolon'),
    ('public class Main { public static void main(String[] args) { absent(); } }', 'JavaCompileError.MissingSymbol'),
    ('public class Main { int x = "a"; }', 'JavaCompileError.IncompatibleTypes'),
    ('import nonexistent.pkg.Foo; public class Main {}', 'JavaCompileError.MissingPackage'),
    ('public class Main { int run() {} }', 'JavaCompileError.MissingReturn'),
    ('public class Main { void run() { return; int x = 1; } }', 'JavaCompileError.UnreachableStatement'),
    ('public class Main { final int x = 1; void run() { x = 2; } }', 'JavaCompileError.FinalAssignment'),
    ('public class Main {', 'JavaCompileError.UnexpectedEOF'),
]


@pytest.mark.parametrize('program,expected', REAL_JAVA)
def test_real_javac_diagnostics(tmp_path, program, expected):
    javac = shutil.which('javac')
    if not javac:
        pytest.skip('javac not installed')
    source = tmp_path / 'Main.java'
    source.write_text(program, encoding='utf-8')
    result = subprocess.run([javac, '-J-Duser.language=en', '-J-Duser.country=US', str(source)], capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    identified = classify(result.stderr)
    assert identified and identified['name'] == expected, result.stderr


REAL_C = [
    ('int main(void) { int x = 1 return x; }', 'CCompileError.MissingSemicolon'),
    ('int main(void) { return absent; }', 'CCompileError.UndeclaredName'),
    ('#include "definitely_missing_header.h"\nint main(void) { return 0; }', 'CCompileError.MissingHeader'),
    ('Mystery value;', 'CCompileError.UnknownType'),
    ('int run(int a); int main(void) { return run(); }', 'CCompileError.TooFewArguments'),
    ('int run(void); int main(void) { return run(1); }', 'CCompileError.TooManyArguments'),
    ('int main(void) { int value = 1; return value(); }', 'CCompileError.NotCallable'),
    ('int main(void) { int value = 1; return *value; }', 'CCompileError.InvalidDereference'),
]


@pytest.mark.parametrize('program,expected', REAL_C)
def test_real_c_compiler_diagnostics(tmp_path, program, expected, monkeypatch):
    compiler = shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        pytest.skip('GCC/Clang not installed')
    source = tmp_path / 'main.c'
    source.write_text(program, encoding='utf-8')
    env = dict(os.environ, LC_ALL='C')
    result = subprocess.run([compiler, '-fsyntax-only', '-fmax-errors=1', str(source)] if Path(compiler).name.startswith('gcc') else [compiler, '-fsyntax-only', '-ferror-limit=1', str(source)], capture_output=True, text=True, env=env, timeout=20)
    assert result.returncode != 0
    identified = classify(result.stderr)
    assert identified and identified['name'] == expected, result.stderr
