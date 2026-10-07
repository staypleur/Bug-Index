import pytest

from scripts.import_java_catalog import throws


def parse(body, imports=''):
    return throws(f'package example; {imports} public class App {{ void run(int count) {{ {body} }} }}'.encode())


def test_actual_throw_statements_and_variable_values():
    items = parse('throw new IllegalArgumentException("Expected at least " + count + " columns in the matrix");')
    assert items[0]['exception'] == 'java.lang.IllegalArgumentException'
    assert items[0]['template'] == 'Expected at least \x00 columns in the matrix'
    assert parse('// throw new IllegalArgumentException("This is commented documentation");\nreturn;') == []
    assert parse('throw new IllegalArgumentException(computeMessage());') == []
    assert parse('throw new IllegalArgumentException("too short");') == []
    assert parse('throw new IllegalArgumentException("Extra cause changes constructor proof", cause);') == []


def test_imports_resolve_exception_identity_and_do_not_guess_custom_classes():
    assert parse('throw new IOException("Unable to read the requested data file");') == []
    assert parse('throw new IOException("Unable to read the requested data file");', 'import custom.IOException;') == []
    assert parse('throw new IOException("Unable to read the requested data file");', 'import java.io.IOException;')[0]['exception'] == 'java.io.IOException'
    assert parse('throw new custom.IllegalArgumentException("Do not infer an overridden constructor");') == []
    assert parse('throw new CustomFailureException("Do not assume how custom messages print");') == []


def test_string_formatter_and_java_escape_semantics():
    item = parse('throw new IllegalArgumentException(String.format("Expected %d matrix columns, got %s", count, name));')[0]
    assert item['template'] == 'Expected \x00 matrix columns, got \x00'
    item = parse(r'throw new IllegalArgumentException("First diagnostic line\nSecond diagnostic line");')[0]
    assert item['template'] == 'First diagnostic line Second diagnostic line'
    assert parse('throw new IllegalArgumentException(String.format(Locale.ROOT, "Expected %d matrix columns", count));') == []


def test_only_known_precondition_semantics_are_supported():
    assert parse('Assert.notNull(value, "A connection is required for the data source");', 'import org.springframework.util.Assert;')[0]['exception'] == 'java.lang.IllegalArgumentException'
    assert parse('Assert.state(ready, "The server must be started before accepting requests");', 'import org.springframework.util.Assert;')[0]['exception'] == 'java.lang.IllegalStateException'
    assert parse('Objects.requireNonNull(value, "The request handler must be specified");', 'import java.util.Objects;')[0]['exception'] == 'java.lang.NullPointerException'
    assert parse('checkArgument(valid, "At least one matrix column is required");', 'import static com.google.common.base.Preconditions.checkArgument;')[0]['exception'] == 'java.lang.IllegalArgumentException'
    assert parse('Assert.notNull(value, "Do not assume a custom assertion implementation");', 'import custom.Assert;') == []
    assert parse('Assert.notNull(value, () -> "Do not infer dynamically supplied messages");', 'import org.springframework.util.Assert;') == []


def test_parse_errors_are_not_treated_as_valid_diagnostics():
    assert throws(b'not a Java file: throw new IllegalArgumentException("Do not parse source with a regex");') == []
