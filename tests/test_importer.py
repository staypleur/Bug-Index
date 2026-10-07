import ast

from scripts.import_library_catalog import Raises, template


def collect(source):
    visitor = Raises()
    visitor.visit(ast.parse(source))
    return visitor.items


def test_only_static_exception_templates_with_enough_information_are_imported():
    assert collect('raise ValueError("A matrix must contain at least one column")')[0][0] == 'ValueError'
    assert collect('raise ValueError(f"A matrix must have {n} columns")')[0][1] == 'A matrix must have \x00 columns'
    assert collect('raise ValueError(message_from_user)') == []
    assert collect('raise ValueError("bad")') == []
    assert collect('raise UserWarning("This operation has been deprecated")') == []
    assert collect('raise CustomError("Custom __str__ might change this message")') == []
    assert collect('raise ValueError("Multiple arguments print a tuple instead", second)') == []
    assert collect('raise KeyError("KeyError uses repr rather than str for its argument")') == []
    assert collect('from custom import ValueError\nraise ValueError("Overridden exception string method")') == []
    assert collect('raise IOError("Unable to open the specified source file")')[0][0] == 'OSError'


def test_variables_are_not_assumed_to_have_one_value_across_branches_or_calls():
    assert collect('if condition:\n msg="First sufficiently descriptive message"\nelse:\n msg="Second sufficiently descriptive message"\nraise ValueError(msg)') == []
    assert collect('msg="A sufficiently descriptive global message"\ndef f(msg):\n raise ValueError(msg)') == []
    assert collect('for x in values:\n msg="A sufficiently descriptive loop message"\nraise ValueError(msg)') == []


def test_literal_formats_and_escaped_braces():
    assert template(ast.parse('"Expected %d columns, got %s" % values', mode='eval').body, {}) == 'Expected \x00 columns, got \x00'
    assert template(ast.parse('"Expected {count} columns; {{literal}}".format(count=n)', mode='eval').body, {}) == 'Expected \x00 columns; {literal}'
    assert template(ast.parse('"Expected {count:{width}} columns".format(count=n, width=w)', mode='eval').body, {}) == 'Expected \x00 columns'
