import os
import shutil
import subprocess
import pytest
from server.catalog import CATALOG, classify, diagnostic


def test_c_scope_static_codes_unicode_quotes_and_unknown_msvc():
    gcc = next(e for e in CATALOG if e.get('c_kind') == 'compiler-template' and "'\x00'" in e['message_template'])
    assert classify(gcc['sample'].replace("'", '’'))['id'] == gcc['id']
    assert classify('main.c:2:1: error: Null pointer dereference [nullPointer]')['name'].endswith('.nullPointer')
    assert classify('main.c(2): error C2065: absent: undeclared identifier')['name'].endswith('.C2065')
    assert classify('main.c(2): error C9999: new compiler error') is None
    assert diagnostic('main.c(2): error C9999: new compiler error')['language'] == 'C'
    assert classify('main.cpp(2): error C2065: absent: undeclared identifier') is None
    assert classify('main.cpp:2: error: some C++ diagnostic') is None
    assert classify('main.c:2:1: warning: Null pointer dereference [nullPointer]') is None
    assert classify('main.c(2): warning C4100: unused parameter') is None


def test_linker_context_and_variable_values_keep_species():
    entry = next(e for e in CATALOG if e.get('c_kind') == 'linker-template' and '\x00' in e['message_template'])
    assert classify(entry['sample'].replace('sample_value', 'another_value'))['id'] == entry['id']
    assert classify(entry['sample'].split('\n', 1)[1]) is None
    assert classify(entry['sample'].split('\n', 1)[1], 'C')['id'] == entry['id']
    assert classify('main.c\nmain.obj : error LNK2019: unresolved external symbol absent')['family_id'] == 21
    assert classify('main.cpp\nmain.obj : error LNK2019: unresolved external symbol absent') is None


@pytest.mark.parametrize('tool,program,label', [
    ('gcc', 'int main(void) { goto absent; }', 'used but not defined'),
    ('gcc', 'struct A { int field:100; };', 'exceeds its type'),
    ('clang', '<<<<<<< HEAD\nint a;\n=======\nint b;\n>>>>>>> branch\n', 'version control conflict marker'),
    ('clang', '#define F(x) x\nint value = F(1,2);', 'arguments provided to function-like macro'),
])
def test_actual_new_c_compiler_species(tmp_path, tool, program, label):
    compiler = shutil.which(tool)
    if not compiler:
        pytest.skip(tool + ' is not installed')
    source = tmp_path / 'main.c'
    source.write_text(program)
    limit = '-fmax-errors=1' if tool == 'gcc' else '-ferror-limit=1'
    run = subprocess.run([compiler, '-x', 'c', '-fsyntax-only', limit, str(source)], capture_output=True, text=True, env=dict(os.environ, LC_ALL='C'), timeout=20)
    assert run.returncode != 0
    result = classify(run.stderr)
    assert result and result.get('verification') == 'source-template', run.stderr
    assert label in result['label'], (result, run.stderr)


def test_actual_cppcheck_c_error(tmp_path):
    tool = shutil.which('cppcheck')
    if not tool:
        pytest.skip('Cppcheck is not installed')
    source = tmp_path / 'main.c'
    source.write_text('int main(void) { int *p = 0; return *p; }')
    run = subprocess.run([tool, '--language=c', '--quiet', '--error-exitcode=2', '--template={file}:{line}:{column}: {severity}: {message} [{id}]', str(source)], capture_output=True, text=True, timeout=20)
    assert run.returncode == 2
    result = classify(run.stderr)
    assert result and result['name'].endswith('.nullPointer'), run.stderr


def test_actual_lld_link_error():
    tool = shutil.which('ld.lld')
    if not tool:
        pytest.skip('LLD is not installed')
    run = subprocess.run([tool, 'definitely_missing_c_object.o'], capture_output=True, text=True, timeout=20)
    assert run.returncode != 0
    result = classify(run.stderr, 'C')
    assert result and result['language'] == 'C' and result['category'] == 'Build', run.stderr


@pytest.mark.parametrize('sanitizer,program,label', [
    ('undefined', 'int main(void) { __builtin_unreachable(); }', 'execution reached an unreachable program point'),
    ('address', '#include <stdlib.h>\nint main(void) { return aligned_alloc(3, 17) != 0; }', 'invalid alignment requested in aligned_alloc'),
])
def test_actual_instrumented_c_runtime(tmp_path, sanitizer, program, label):
    tool = shutil.which('clang')
    if not tool or os.name == 'nt':
        pytest.skip('Linux/macOS Clang sanitizer runtime is required')
    source, output = tmp_path / 'main.c', tmp_path / 'app'
    source.write_text(program)
    subprocess.run([tool, '-std=c11', '-g', '-O0', '-fsanitize=' + sanitizer, str(source), '-o', str(output)], check=True, capture_output=True, timeout=30)
    run = subprocess.run([str(output)], capture_output=True, text=True, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1'), timeout=20)
    assert run.returncode != 0
    result = classify(run.stderr, 'C')
    assert result and result.get('verification') == 'source-template', run.stderr
    assert label in result['label'], (result, run.stderr)


@pytest.mark.parametrize('program,code', [
    ('int main(void) { return absent; }', 'C2065'),
    ('#include "definitely_missing_header.h"\nint main(void) { return 0; }', 'C1083'),
])
def test_actual_msvc_c_mode(tmp_path, program, code):
    tool = shutil.which('cl')
    if not tool:
        pytest.skip('MSVC is not installed')
    source = tmp_path / 'main.c'
    source.write_text(program)
    run = subprocess.run([tool, '/nologo', '/TC', '/Zs', str(source)], capture_output=True, text=True, env=dict(os.environ, VSLANG='1033'), timeout=30)
    assert run.returncode != 0
    result = classify(run.stdout + run.stderr)
    assert result and result['name'].endswith('.' + code), run.stdout + run.stderr
