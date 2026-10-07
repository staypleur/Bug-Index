from server.catalog import CATALOG, classify, diagnostic
import shutil
import subprocess
import pytest


def test_android_logcat_formats_preserve_source_identity():
    entry = next(e for e in CATALOG if e.get('package') == 'Android' and e.get('message_template'))
    for prefix in ('10-07 12:34:56.123  123  456 E AndroidRuntime: ', 'E/AndroidRuntime( 123): '):
        log = '\n'.join(prefix + line for line in entry['sample'].splitlines())
        assert classify(log)['id'] == entry['id']
        assert diagnostic(log)['language'] == 'Java'


def test_java_library_origin_is_required_and_chains_use_final_exception():
    entry = next(e for e in CATALOG if e.get('package') == 'Android' and e.get('message_template'))
    unrelated = entry['sample'].split('\n')[0] + '\n\tat example.Main.run(Main.java:12)'
    result = classify(unrelated)
    assert result is None or result['id'] != entry['id']
    unknown = entry['sample'] + '\nCaused by: example.CustomFailureException: final failure\n\tat example.Main.run(Main.java:1)'
    assert classify(unknown) is None


def test_maven_prefix_and_jdk_module_frames():
    entry = next(e for e in CATALOG if e.get('package') == 'OpenJDK' and e.get('message_template'))
    log = entry['sample'].replace('\tat ', '\tat java.base/')
    log = '\n'.join('[ERROR] ' + line for line in log.splitlines())
    assert classify(log)['id'] == entry['id']


@pytest.mark.parametrize('capacity', [-1, -77])
def test_actual_jdk_runtime_message_values_share_species(tmp_path, capacity):
    javac, java = shutil.which('javac'), shutil.which('java')
    if not javac or not java:
        pytest.skip('JDK is not installed')
    source = tmp_path / 'Main.java'
    source.write_text('public class Main { public static void main(String[] args) { new java.util.HashMap<Object,Object>(' + str(capacity) + '); } }')
    subprocess.run([javac, str(source)], check=True, capture_output=True, timeout=20)
    run = subprocess.run([java, '-cp', str(tmp_path), 'Main'], capture_output=True, text=True, timeout=20)
    assert run.returncode != 0
    entry = classify(run.stderr)
    assert entry and entry['package'] == 'OpenJDK'
    expected = next(e for e in CATALOG if e.get('package') == 'OpenJDK' and e.get('message_template') == 'Illegal initial capacity: \x00')
    assert entry['id'] == expected['id']
