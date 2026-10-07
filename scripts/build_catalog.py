"""Build the same append-only diagnostic catalog for the API and VS Code.

IDs 1..21 are the original release's database identities. Never reorder or delete
published entries. New IDs are explicit so inserting a rule cannot renumber data.
Samples are diagnostic fixtures, not claims that every compiler version uses them.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_SOURCE = "https://docs.python.org/3/library/exceptions.html"
JAVA_SOURCE = "https://docs.oracle.com/en/java/javase/21/docs/api/"
C_SOURCE = "https://clang.llvm.org/docs/DiagnosticsReference.html"
ASAN_SOURCE = "https://clang.llvm.org/docs/AddressSanitizer.html"
UBSAN_SOURCE = "https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html"


def catalog():
    entries = []

    def add(number, name, language, category, rarity, icon, pattern, sample,
            family=None, label=None, priority=0, source=None):
        parent = next((e for e in entries if e['id'] == family), None)
        entries.append(dict(id=number, name=name, language=language, category=category,
                            rarity=rarity, icon=icon, pattern=pattern, sample=sample,
                            family_id=family or number, family_name=parent['name'] if parent else name,
                            label=label or name, priority=priority,
                            source=source or {'Python': PYTHON_SOURCE, 'Java': JAVA_SOURCE, 'C': C_SOURCE}[language]))

    def py(name):
        return rf"^[ \t]*(?:[|+]\s*)?{name}(?::|$)"

    def java(name):
        return rf'^[ \t]*(?:(?:Exception in thread "[^"\n]+"|Caused by:|Suppressed:)\s+)?(?:[\w$]+\.)*{name}(?::|$)'

    java_location = r'^[ \t]*[^"\'=\n]+\.java:\d+:\s*error:'
    c_location = r'^[ \t]*[^"\'=\n]+\.(?:c|h):\d+(?::\d+)?:\s*(?:fatal )?error:'
    ub_location = r'^[ \t]*[^"\'=\n]+\.(?:c|h):\d+(?::\d+)?:\s*runtime error:'

    # Keep the original fallback types and their IDs. Only known messages refine them.
    legacy = [
        (1, 'NullPointerException', 'Java', 'Runtime', 'Uncommon', '🪲', java('NullPointerException'), 'java.lang.NullPointerException: unspecified'),
        (2, 'ArrayIndexOutOfBoundsException', 'Java', 'Runtime', 'Uncommon', '🐜', java('ArrayIndexOutOfBoundsException'), 'java.lang.ArrayIndexOutOfBoundsException: unspecified'),
        (3, 'ClassNotFoundException', 'Java', 'Dependency', 'Uncommon', '🦗', java('ClassNotFoundException'), 'java.lang.ClassNotFoundException: Example'),
        (4, 'IllegalArgumentException', 'Java', 'Runtime', 'Common', '🐞', java('IllegalArgumentException'), 'java.lang.IllegalArgumentException: bad input'),
        (5, 'StackOverflowError', 'Java', 'Memory', 'Rare', '🕷', java('StackOverflowError'), 'java.lang.StackOverflowError'),
        (6, 'OutOfMemoryError', 'Java', 'Memory', 'Epic', '🦂', java('OutOfMemoryError'), 'java.lang.OutOfMemoryError: unspecified'),
        (7, 'JavaCompileError', 'Java', 'Build', 'Common', '🐝', java_location, 'Main.java:2: error: unspecified diagnostic'),
        (8, 'SyntaxError', 'Python', 'Syntax', 'Common', '🐛', py('SyntaxError'), 'SyntaxError: custom diagnostic'),
        (9, 'TypeError', 'Python', 'Runtime', 'Common', '🐞', py('TypeError'), 'TypeError: bad input'),
        (10, 'NameError', 'Python', 'Runtime', 'Common', '🐜', py('NameError'), 'NameError: custom diagnostic'),
        (11, 'IndexError', 'Python', 'Runtime', 'Uncommon', '🪲', py('IndexError'), 'IndexError: custom diagnostic'),
        (12, 'KeyError', 'Python', 'Runtime', 'Uncommon', '🦗', py('KeyError'), "KeyError: 'missing'"),
        (13, 'ZeroDivisionError', 'Python', 'Runtime', 'Common', '🐝', py('ZeroDivisionError'), 'ZeroDivisionError: custom diagnostic'),
        (14, 'ModuleNotFoundError', 'Python', 'Dependency', 'Uncommon', '🦋', py('ModuleNotFoundError'), 'ModuleNotFoundError: custom diagnostic'),
        (15, 'ValueError', 'Python', 'Runtime', 'Common', '🐛', py('ValueError'), 'ValueError: custom diagnostic'),
        (16, 'Segmentation Fault', 'C', 'Memory', 'Rare', '🦂', r'^.*(?:segmentation fault|sigsegv|access violation)', 'Segmentation fault (core dumped)'),
        (17, 'Buffer Overflow', 'C', 'Memory', 'Epic', '🕷', r'^.*(?:(?:heap|stack|global)-buffer-overflow|stack smashing detected)', '*** stack smashing detected ***: terminated'),
        (18, 'Use After Free', 'C', 'Memory', 'Epic', '🦂', r'^.*heap-use-after-free', 'ERROR: AddressSanitizer: heap-use-after-free'),
        (19, 'Memory Leak', 'C', 'Memory', 'Epic', '🦋', r'^.*LeakSanitizer: detected memory leaks', 'ERROR: LeakSanitizer: detected memory leaks'),
        (20, 'CCompileError', 'C', 'Build', 'Common', '🐝', c_location, 'main.c:2:1: error: unspecified diagnostic'),
        (21, 'Undefined Reference', 'C', 'Build', 'Uncommon', '🦗', r'^.*(?:undefined reference to|Undefined symbols for architecture)', "main.o: undefined reference to `missing'"),
    ]
    for row in legacy:
        add(*row)

    # Python built-in exceptions (excluding warnings, Ctrl-C and normal iteration exits).
    python_types = [
        (22, 'AssertionError', 'Runtime'), (23, 'AttributeError', 'Runtime'),
        (24, 'EOFError', 'OS'), (25, 'MemoryError', 'Memory'), (26, 'OverflowError', 'Runtime'),
        (27, 'RecursionError', 'Runtime'), (28, 'RuntimeError', 'Runtime'),
        (29, 'NotImplementedError', 'Runtime'), (30, 'UnboundLocalError', 'Runtime'),
        (31, 'FileNotFoundError', 'OS'), (32, 'PermissionError', 'OS'),
        (33, 'IsADirectoryError', 'OS'), (34, 'NotADirectoryError', 'OS'),
        (35, 'FileExistsError', 'OS'), (36, 'BrokenPipeError', 'Network'),
        (37, 'ConnectionRefusedError', 'Network'), (38, 'ConnectionResetError', 'Network'),
        (39, 'ConnectionAbortedError', 'Network'), (40, 'TimeoutError', 'Network'),
        (41, 'UnicodeDecodeError', 'Runtime'), (42, 'UnicodeEncodeError', 'Runtime'),
        (43, 'UnicodeTranslateError', 'Runtime'), (44, 'OSError', 'OS'),
        (45, 'BufferError', 'Memory'), (46, 'ImportError', 'Dependency'),
        (47, 'IndentationError', 'Syntax'), (48, 'TabError', 'Syntax'),
        (49, 'ExceptionGroup', 'Runtime'), (50, 'BlockingIOError', 'OS'),
        (51, 'InterruptedError', 'OS'), (52, 'ProcessLookupError', 'OS'),
        (53, 'ChildProcessError', 'OS'),
    ]
    for number, name, category in python_types:
        add(number, name, 'Python', category, 'Rare' if category == 'Memory' else 'Uncommon', '🪲', py(name), name + ': custom diagnostic')

    # Specific messages: every row has a bounded pattern and a positive fixture.
    python_variants = [
        (54, 8, 'InvalidSyntax', '올바르지 않은 문법', r'invalid syntax', 'invalid syntax'),
        (55, 8, 'UnclosedDelimiter', '닫히지 않은 괄호', r'was never closed', "'(' was never closed"),
        (56, 8, 'UnterminatedString', '닫히지 않은 문자열', r'unterminated string literal|EOL while scanning string literal', 'unterminated string literal (detected at line 2)'),
        (57, 8, 'UnterminatedTripleString', '닫히지 않은 여러 줄 문자열', r'unterminated triple-quoted string literal|EOF while scanning triple-quoted string literal', 'unterminated triple-quoted string literal (detected at line 3)'),
        (58, 8, 'DelimiterMismatch', '짝이 맞지 않는 괄호', r'closing parenthesis .* does not match opening parenthesis', "closing parenthesis ']' does not match opening parenthesis '('"),
        (59, 8, 'AssignmentTarget', '대입할 수 없는 대상', r'cannot assign to', 'cannot assign to literal here. Maybe you meant == instead of =?'),
        (60, 8, 'ReturnOutsideFunction', '함수 밖의 return', r"'return' outside function", "'return' outside function"),
        (61, 8, 'BreakOutsideLoop', '반복문 밖의 break', r"'break' outside loop", "'break' outside loop"),
        (62, 8, 'ContinueOutsideLoop', '반복문 밖의 continue', r"'continue' not properly in loop", "'continue' not properly in loop"),
        (63, 8, 'AwaitOutsideFunction', '비동기 함수 밖의 await', r"'await' outside (?:async )?function", "'await' outside function"),
        (64, 8, 'MissingColon', '콜론 누락', r"expected ':'", "expected ':'"),
        (65, 8, 'PositionalAfterKeyword', '키워드 인자 뒤의 위치 인자', r'positional argument follows keyword argument', 'positional argument follows keyword argument'),
        (66, 8, 'DuplicateArgument', '함수 인자 이름 중복', r'duplicate argument .* in function definition', "duplicate argument 'x' in function definition"),
        (67, 9, 'UnsupportedOperand', '피연산자 타입 불일치', r'unsupported operand type\(s\)', "unsupported operand type(s) for +: 'int' and 'str'"),
        (68, 9, 'NotCallable', '호출할 수 없는 객체', r'object is not callable', "'int' object is not callable"),
        (69, 9, 'NotSubscriptable', '인덱싱할 수 없는 객체', r'object is not subscriptable', "'NoneType' object is not subscriptable"),
        (70, 9, 'NotIterable', '반복할 수 없는 객체', r'object is not iterable', "'int' object is not iterable"),
        (71, 9, 'Unhashable', '해시할 수 없는 키', r'unhashable type:', "unhashable type: 'list'"),
        (72, 9, 'MissingArgument', '필수 인자 누락', r'missing \d+ required (?:positional|keyword-only) argument', "run() missing 1 required positional argument: 'value'"),
        (73, 9, 'UnexpectedKeyword', '지원하지 않는 키워드 인자', r'unexpected keyword argument', "run() got an unexpected keyword argument 'foo'"),
        (74, 9, 'MultipleArgumentValues', '동일 인자의 값 중복', r'multiple values for argument', "run() got multiple values for argument 'value'"),
        (75, 9, 'ArgumentCount', '위치 인자 개수 불일치', r'takes .* positional arguments? but .* (?:was|were) given', 'run() takes 1 positional argument but 2 were given'),
        (76, 9, 'NoLength', '길이를 구할 수 없는 객체', r'has no len\(\)', "object of type 'int' has no len()"),
        (77, 9, 'ImmutableAssignment', '변경할 수 없는 객체', r'does not support item assignment', "'tuple' object does not support item assignment"),
        (78, 9, 'InvalidIndexType', '인덱스 타입 불일치', r'indices must be integers', 'list indices must be integers or slices, not str'),
        (79, 9, 'StringConcatenation', '문자열 결합 타입 불일치', r'can only concatenate str', 'can only concatenate str (not "int") to str'),
        (80, 10, 'UndefinedName', '정의되지 않은 이름', r"name .+ is not defined", "name 'missing' is not defined"),
        (81, 11, 'ListIndex', '리스트 인덱스 범위 초과', r'list index out of range', 'list index out of range'),
        (82, 11, 'StringIndex', '문자열 인덱스 범위 초과', r'string index out of range', 'string index out of range'),
        (83, 11, 'TupleIndex', '튜플 인덱스 범위 초과', r'tuple index out of range', 'tuple index out of range'),
        (84, 11, 'EmptyPop', '빈 리스트에서 pop', r'pop from empty list', 'pop from empty list'),
        (85, 13, 'Division', '0으로 나누기', r'^division by zero', 'division by zero'),
        (86, 13, 'IntegerDivision', '정수 나눗셈·나머지 0 오류', r'integer division or modulo by zero', 'integer division or modulo by zero'),
        (87, 13, 'Modulo', '실수 0으로 나머지 연산', r'float modulo(?: by zero)?', 'float modulo'),
        (88, 15, 'InvalidInteger', '정수 변환 실패', r'invalid literal for int\(\)', "invalid literal for int() with base 10: 'abc'"),
        (89, 15, 'InvalidFloat', '실수 변환 실패', r'could not convert string to float', "could not convert string to float: 'abc'"),
        (90, 15, 'TooManyUnpack', '언패킹 값이 너무 많음', r'too many values to unpack', 'too many values to unpack (expected 2)'),
        (91, 15, 'TooFewUnpack', '언패킹 값이 부족함', r'not enough values to unpack', 'not enough values to unpack (expected 2, got 1)'),
        (92, 15, 'MissingListValue', '리스트에서 값 찾기 실패', r'list\.remove\(x\): x not in list|is not in list', 'list.remove(x): x not in list'),
        (93, 15, 'MathDomain', '수학 함수의 정의역 벗어남', r'math domain error', 'math domain error'),
        (94, 23, 'MissingAttribute', '존재하지 않는 속성', r'has no attribute', "'NoneType' object has no attribute 'name'"),
        (95, 30, 'UninitializedLocal', '값을 넣기 전 지역 변수 사용', r'not associated with a value|referenced before assignment', "cannot access local variable 'x' where it is not associated with a value"),
        (96, 46, 'MissingImportName', '가져올 이름을 찾지 못함', r'cannot import name', "cannot import name 'missing' from 'module'"),
        (97, 46, 'RelativeImport', '상위 패키지가 없는 상대 import', r'attempted relative import', 'attempted relative import with no known parent package'),
        (98, 47, 'ExpectedBlock', '들여쓴 블록 누락', r'expected an indented block', "expected an indented block after 'if' statement on line 1"),
        (99, 47, 'UnexpectedIndent', '불필요한 들여쓰기', r'unexpected indent', 'unexpected indent'),
        (100, 47, 'IndentMismatch', '들여쓰기 깊이 불일치', r'unindent does not match any outer indentation level', 'unindent does not match any outer indentation level'),
    ]
    for number, family, suffix, label, message_pattern, message in python_variants:
        parent = next(e for e in entries if e['id'] == family)
        # Anchor all specificity rules to an actual exception line.
        message_pattern = message_pattern.removeprefix('^')
        add(number, parent['name'] + '.' + suffix, 'Python', parent['category'], parent['rarity'], parent['icon'],
            py(parent['name']).replace('(?::|$)', ':') + r'[^\n]*(?:' + message_pattern + ')', parent['name'] + ': ' + message,
            family, label, priority=100)

    java_types = [
        (101, 'ArithmeticException', 'Runtime'), (102, 'ClassCastException', 'Runtime'),
        (103, 'IndexOutOfBoundsException', 'Runtime'), (104, 'StringIndexOutOfBoundsException', 'Runtime'),
        (105, 'ArrayStoreException', 'Runtime'), (106, 'NegativeArraySizeException', 'Runtime'),
        (107, 'NumberFormatException', 'Runtime'), (108, 'UnsupportedOperationException', 'Runtime'),
        (109, 'IllegalStateException', 'Runtime'), (110, 'IllegalMonitorStateException', 'Runtime'),
        (111, 'SecurityException', 'OS'), (112, 'ConcurrentModificationException', 'Runtime'),
        (113, 'NoSuchElementException', 'Runtime'), (114, 'IOException', 'OS'),
        (115, 'FileNotFoundException', 'OS'), (116, 'EOFException', 'OS'),
        (117, 'InterruptedIOException', 'OS'), (118, 'UncheckedIOException', 'OS'),
        (119, 'SocketException', 'Network'), (120, 'SocketTimeoutException', 'Network'),
        (121, 'ConnectException', 'Network'), (122, 'UnknownHostException', 'Network'),
        (123, 'MalformedURLException', 'Network'), (124, 'URISyntaxException', 'Network'),
        (125, 'InterruptedException', 'Runtime'), (126, 'NoSuchMethodException', 'Runtime'),
        (127, 'NoSuchFieldException', 'Runtime'), (128, 'IllegalAccessException', 'Runtime'),
        (129, 'InvocationTargetException', 'Runtime'), (130, 'InstantiationException', 'Runtime'),
        (131, 'NoClassDefFoundError', 'Dependency'), (132, 'UnsupportedClassVersionError', 'Build'),
        (133, 'ExceptionInInitializerError', 'Runtime'), (134, 'LinkageError', 'Dependency'),
        (135, 'AbstractMethodError', 'Dependency'), (136, 'UnsatisfiedLinkError', 'Dependency'),
        (137, 'NoSuchMethodError', 'Dependency'), (138, 'NoSuchFieldError', 'Dependency'),
    ]
    for number, name, category in java_types:
        package = 'java.lang'
        if 112 <= number <= 113: package = 'java.util'
        if 114 <= number <= 118: package = 'java.io'
        if 119 <= number <= 124: package = 'java.net'
        if number == 129: package = 'java.lang.reflect'
        add(number, name, 'Java', category, 'Uncommon', '🪲', java(name), 'Exception in thread "main" ' + package + '.' + name + ': custom diagnostic')

    java_variants = [
        (139, 1, 'MethodCall', 'null 객체의 메서드 호출', r'Cannot invoke', 'Cannot invoke "User.name()" because "user" is null'),
        (140, 1, 'FieldRead', 'null 객체의 필드 읽기', r'Cannot read field', 'Cannot read field "name" because "user" is null'),
        (141, 1, 'FieldWrite', 'null 객체의 필드 쓰기', r'Cannot assign field', 'Cannot assign field "name" because "user" is null'),
        (142, 1, 'ArrayRead', 'null 배열 읽기', r'Cannot load from', 'Cannot load from int array because "values" is null'),
        (143, 1, 'ArrayWrite', 'null 배열 쓰기', r'Cannot store to', 'Cannot store to int array because "values" is null'),
        (144, 1, 'ArrayLength', 'null 배열의 길이 조회', r'Cannot read the array length', 'Cannot read the array length because "values" is null'),
        (145, 1, 'Monitor', 'null 객체의 동기화 잠금', r'Cannot enter synchronized block', 'Cannot enter synchronized block because "lock" is null'),
        (146, 1, 'ThrowNull', 'null 예외 던지기', r'Cannot throw exception', 'Cannot throw exception because "error" is null'),
        (147, 6, 'HeapSpace', 'Java 힙 메모리 부족', r'Java heap space', 'Java heap space'),
        (148, 6, 'GCOverhead', 'GC 처리 한도 초과', r'GC overhead limit exceeded', 'GC overhead limit exceeded'),
        (149, 6, 'Metaspace', '클래스 메타데이터 메모리 부족', r'Metaspace', 'Metaspace'),
        (150, 6, 'NativeThread', '새 네이티브 스레드 생성 실패', r'unable to create (?:new )?native thread', 'unable to create native thread'),
        (151, 6, 'ArraySize', 'VM 배열 크기 한도 초과', r'Requested array size exceeds VM limit', 'Requested array size exceeds VM limit'),
        (152, 101, 'Division', '정수 0으로 나누기', r'/ by zero', '/ by zero'),
        (153, 121, 'Refused', '연결 거부', r'Connection refused', 'Connection refused'),
        (154, 119, 'Reset', '소켓 연결 초기화', r'Connection reset', 'Connection reset'),
        (155, 119, 'BrokenPipe', '끊어진 소켓에 쓰기', r'Broken pipe', 'Broken pipe'),
        (156, 120, 'ReadTimeout', '소켓 읽기 시간 초과', r'Read timed out', 'Read timed out'),
        (157, 107, 'InvalidNumber', '문자열 숫자 변환 실패', r'For input string:', 'For input string: "abc"'),
    ]
    for number, family, suffix, label, message_pattern, message in java_variants:
        parent = next(e for e in entries if e['id'] == family)
        add(number, parent['name'] + '.' + suffix, 'Java', parent['category'], parent['rarity'], parent['icon'],
            java(parent['name']).replace('(?::|$)', ':') + r'[^\n]*(?:' + message_pattern + ')',
            'java.lang.' + parent['name'] + ': ' + message, family, label, priority=100)

    java_build = [
        (158, 'MissingSemicolon', '세미콜론 누락', r"';' expected", "';' expected"),
        (159, 'MissingSymbol', '심볼을 찾지 못함', r'cannot find symbol', 'cannot find symbol'),
        (160, 'IncompatibleTypes', '호환되지 않는 타입', r'incompatible types', 'incompatible types: String cannot be converted to int'),
        (161, 'MissingPackage', '패키지를 찾지 못함', r'package .+ does not exist', 'package example does not exist'),
        (162, 'DuplicateVariable', '변수 중복 선언', r'variable .+ is already defined', 'variable value is already defined in method main(String[])'),
        (163, 'UninitializedVariable', '초기화하지 않은 변수', r'variable .+ might not have been initialized', 'variable value might not have been initialized'),
        (164, 'MissingReturn', '반환문 누락', r'missing return statement', 'missing return statement'),
        (165, 'UnreachableStatement', '도달할 수 없는 문장', r'unreachable statement', 'unreachable statement'),
        (166, 'StaticContext', '정적 문맥에서 인스턴스 접근', r'non-static .+ cannot be referenced from a static context', 'non-static variable value cannot be referenced from a static context'),
        (167, 'MethodArguments', '메서드 인자 불일치', r'(?:method|constructor) .+ cannot be applied to given types', 'method run in class Main cannot be applied to given types;'),
        (168, 'ClassFileName', '공개 클래스와 파일명 불일치', r'class .+ is public, should be declared in a file named', 'class Example is public, should be declared in a file named Example.java'),
        (169, 'AccessControl', '접근 권한 위반', r'has private access|has protected access|is not public .* cannot be accessed', 'value has private access in User'),
        (170, 'UnhandledException', '체크 예외 처리 누락', r'unreported exception .+ must be caught or declared', 'unreported exception IOException; must be caught or declared to be thrown'),
        (171, 'MissingOverride', '추상 메서드 구현 누락', r'is not abstract and does not override abstract method', 'Main is not abstract and does not override abstract method run() in Task'),
        (172, 'FinalAssignment', 'final 값 재대입', r'cannot assign a value to final variable', 'cannot assign a value to final variable value'),
        (173, 'IllegalExpression', '표현식 시작 오류', r'illegal start of expression', 'illegal start of expression'),
        (174, 'UnexpectedEOF', '닫히지 않은 코드 블록', r'reached end of file while parsing', 'reached end of file while parsing'),
        (175, 'UnclosedString', '닫히지 않은 문자열', r'unclosed string literal', 'unclosed string literal'),
        (176, 'MissingIdentifier', '식별자 누락', r'<identifier> expected', '<identifier> expected'),
        (177, 'DuplicateClass', '클래스 중복 정의', r'duplicate class:', 'duplicate class: Example'),
    ]
    for number, suffix, label, pattern, message in java_build:
        add(number, 'JavaCompileError.' + suffix, 'Java', 'Build', 'Common', '🐝',
            java_location + r'[^\n]*(?:' + pattern + ')',
            'Main.java:2: error: ' + message, 7, label, priority=100)

    c_build = [
        (178, 'MissingSemicolon', '세미콜론 누락', r"expected (?:[‘'],[’'] or )?[‘'];[’']", "expected ';' before 'return'"),
        (179, 'UndeclaredName', '선언되지 않은 이름', r'.+ undeclared|use of undeclared identifier', "'value' undeclared (first use in this function)"),
        (180, 'MissingHeader', '헤더 파일을 찾지 못함', r'.+\.h: No such file or directory|.+\.h[’\']? file not found', 'missing.h: No such file or directory'),
        (181, 'UnknownType', '알 수 없는 타입 이름', r'unknown type name', "unknown type name 'Thing'"),
        (182, 'TooFewArguments', '함수 인자 부족', r'too few arguments', "too few arguments to function 'run'"),
        (183, 'TooManyArguments', '함수 인자 초과', r'too many arguments', "too many arguments to function 'run'"),
        (184, 'ConflictingTypes', '선언과 정의의 타입 충돌', r'conflicting types for', "conflicting types for 'run'"),
        (185, 'Redefinition', '이름 중복 정의', r'redefinition of', "redefinition of 'value'"),
        (186, 'ExpectedExpression', '표현식 누락', r'expected expression', "expected expression before ')' token"),
        (187, 'ExpectedIdentifier', '식별자 누락', r'expected identifier', 'expected identifier or ( before numeric constant'),
        (188, 'NotCallable', '함수가 아닌 객체 호출', r'called object .+ is not a function|called object type .+ is not a function', "called object 'value' is not a function or function pointer"),
        (189, 'InvalidDereference', '포인터가 아닌 값 역참조', r'invalid type argument of unary|indirection requires pointer operand', 'invalid type argument of unary * (have int)'),
        (190, 'InvalidOperands', '연산자의 피연산자 타입 오류', r'invalid operands to|invalid operands to binary expression', 'invalid operands to binary + (have int and struct User)'),
        (191, 'MissingMember', '구조체 멤버를 찾지 못함', r'has no member named|no member named', "'struct User' has no member named 'name'"),
        (192, 'InvalidMemberAccess', '구조체가 아닌 값의 멤버 접근', r'request for member .+ in something not a structure|member reference base type .+ is not a structure', "request for member 'name' in something not a structure or union"),
        (193, 'NotSubscriptable', '배열이 아닌 값 인덱싱', r'subscripted value is not an array|subscripted value is neither array nor pointer', 'subscripted value is neither array nor pointer nor vector'),
        (194, 'InvalidLvalue', '대입할 수 없는 대상', r'lvalue required|expression is not assignable', 'lvalue required as left operand of assignment'),
        (195, 'ReadOnlyAssignment', '읽기 전용 값에 대입', r'assignment of read-only|cannot assign to variable .+ const-qualified', "assignment of read-only variable 'value'"),
        (196, 'InvalidInitializer', '초깃값 오류', r'invalid initializer', 'invalid initializer'),
        (197, 'NonConstantInitializer', '상수식이 아닌 초깃값', r'initializer element is not constant|initializer element is not a compile-time constant', 'initializer element is not constant'),
        (198, 'UnterminatedString', '닫히지 않은 문자열', r'missing terminating .+ character', 'missing terminating " character'),
        (199, 'UnexpectedEOF', '닫히지 않은 코드 블록', r'expected declaration or statement at end of input|expected .+ at end of input', 'expected declaration or statement at end of input'),
        (200, 'DuplicateCase', 'switch case 값 중복', r'duplicate case value', 'duplicate case value'),
        (201, 'CaseOutsideSwitch', 'switch 밖의 case', r'case label not within a switch', 'case label not within a switch statement'),
        (202, 'BreakOutsideLoop', '반복문·switch 밖의 break', r'break statement not within loop or switch', 'break statement not within loop or switch'),
        (203, 'ContinueOutsideLoop', '반복문 밖의 continue', r'continue statement not within a loop', 'continue statement not within a loop'),
        (204, 'InvalidArraySize', '잘못된 배열 크기', r'size of array .+ is negative|array size is negative', "size of array 'values' is negative"),
        (205, 'IncompleteType', '완전하지 않은 타입', r'invalid use of incomplete|storage size of .+ isn.t known|incomplete type', "storage size of 'user' isn't known"),
        (206, 'IncompatibleTypes', '호환되지 않는 타입', r'incompatible types|incompatible .+ conversion', 'incompatible types when assigning to type int from type struct User'),
        (207, 'ImplicitFunction', '선언되지 않은 함수 호출', r'implicit declaration of function|call to undeclared function', "implicit declaration of function 'run'"),
    ]
    for number, suffix, label, pattern, message in c_build:
        add(number, 'CCompileError.' + suffix, 'C', 'Build', 'Common', '🐝',
            c_location + r'[^\n]*(?:' + pattern + ')',
            'main.c:2:1: error: ' + message, 20, label, priority=100)

    # Sanitizer diagnostics are only collected when the runtime reports them.
    sanitizer = [
        (208, 17, 'Heap', '힙 버퍼 범위 초과', 'heap-buffer-overflow'),
        (209, 17, 'Stack', '스택 버퍼 범위 초과', 'stack-buffer-overflow'),
        (210, 17, 'Global', '전역 버퍼 범위 초과', 'global-buffer-overflow'),
        (211, None, 'StackUseAfterReturn', '함수 반환 뒤 스택 접근', 'stack-use-after-return'),
        (212, None, 'StackUseAfterScope', '범위를 벗어난 스택 변수 접근', 'stack-use-after-scope'),
        (213, None, 'DoubleFree', '메모리 이중 해제', 'attempting double-free'),
        (214, None, 'InvalidFree', '할당하지 않은 주소 해제', 'attempting free on address which was not malloc'),
        (216, None, 'NegativeAllocation', '음수 크기 메모리 할당', 'negative-size-param'),
        (217, None, 'AllocationTooLarge', '메모리 할당 한도 초과', 'allocation-size-too-big'),
        (218, None, 'MemcpyOverlap', '겹치는 메모리 영역 복사', 'memcpy-param-overlap'),
    ]
    for number, family, suffix, label, diagnostic in sanitizer:
        parent = next((e for e in entries if e['id'] == family), None)
        name = parent['name'] + '.' + suffix if parent else suffix
        add(number, name, 'C', 'Memory', 'Epic', '🦂', r'^.*AddressSanitizer:\s*' + diagnostic,
            'ERROR: AddressSanitizer: ' + diagnostic, family, label, priority=100, source=ASAN_SOURCE)

    ub = [
        (220, 'SignedOverflow', '부호 있는 정수 오버플로', r'signed integer overflow', 'signed integer overflow: 2147483647 + 1 cannot be represented in type int'),
        (221, 'DivisionByZero', '정수 0으로 나누기', r'division by zero', 'division by zero'),
        (222, 'InvalidShift', '잘못된 비트 시프트', r'shift exponent .* (?:too large|negative)|left shift of negative value', 'shift exponent 32 is too large for 32-bit type int'),
        (223, 'NullDereference', 'NULL 포인터 역참조', r'(?:load of|store to|member access within) null pointer', 'load of null pointer of type int'),
        (224, 'MisalignedAccess', '정렬되지 않은 메모리 접근', r'misaligned address', 'load of misaligned address 0x123 for type int'),
        (225, 'OutOfBounds', '배열 경계 초과', r'index .* out of bounds', 'index 5 out of bounds for type int[3]'),
        (226, 'InvalidBool', 'bool 값 표현 오류', r'not a valid value for type .?bool', 'load of value 3, which is not a valid value for type bool'),
        (227, 'PointerOverflow', '포인터 주소 계산 오버플로', r'pointer index expression .* overflowed|addition of unsigned offset .* overflowed', 'pointer index expression with base 0x1 overflowed to 0xffff'),
    ]
    for number, suffix, label, pattern, message in ub:
        add(number, 'UndefinedBehavior.' + suffix, 'C', 'Runtime', 'Rare', '🕷',
            ub_location + r'[^\n]*(?:' + pattern + ')',
            'main.c:2:1: runtime error: ' + message, label=label, priority=100, source=UBSAN_SOURCE)

    # A reviewed extraction pipeline supplies source-backed library templates.
    # Fixed IDs live in the committed snapshot; downloading never happens at runtime.
    library_path = ROOT / 'server/library_templates.json'
    java_libraries = [
        (300, 'Spring', 'org.springframework.beans.factory.BeanCreationException', '빈 생성 실패', 'https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/beans/factory/BeanCreationException.html'),
        (301, 'Spring', 'org.springframework.beans.factory.BeanCreationNotAllowedException', '현재 단계에서 빈 생성 불가', 'https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/beans/factory/BeanCreationNotAllowedException.html'),
        (302, 'Spring', 'org.springframework.beans.factory.BeanCurrentlyInCreationException', '생성 중인 빈의 순환 의존', 'https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/beans/factory/BeanCurrentlyInCreationException.html'),
        (303, 'Spring', 'org.springframework.beans.factory.BeanIsAbstractException', '추상 빈 인스턴스 생성 실패', 'https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/beans/factory/BeanIsAbstractException.html'),
        (304, 'Spring', 'org.springframework.beans.factory.support.ScopeNotActiveException', '활성화되지 않은 빈 범위', 'https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/beans/factory/support/ScopeNotActiveException.html'),
        (305, 'Spring', 'org.springframework.beans.factory.UnsatisfiedDependencyException', '빈 의존성 주입 실패', 'https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/beans/factory/UnsatisfiedDependencyException.html'),
        (306, 'Spring', 'org.springframework.dao.DataIntegrityViolationException', '데이터 무결성 제약 위반', 'https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/dao/DataIntegrityViolationException.html'),
        (307, 'Spring', 'org.springframework.dao.DuplicateKeyException', '데이터 키 중복', 'https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/dao/DuplicateKeyException.html'),
        (308, 'Maven', 'org.apache.maven.plugin.MojoExecutionException', 'Maven 플러그인 실행 오류', 'https://maven.apache.org/ref/3.9.11/maven-plugin-api/apidocs/org/apache/maven/plugin/MojoExecutionException.html'),
        (309, 'Gradle', 'org.gradle.api.GradleException', 'Gradle 빌드 오류', 'https://docs.gradle.org/current/javadoc/org/gradle/api/GradleException.html'),
    ]
    for number, package, name, label, source in java_libraries:
        pattern = r'^[ \t]*(?:(?:Exception in thread "[^"\n]+"|Caused by:|Suppressed:)\s+)?' + re.escape(name) + r'(?::|$)'
        add(number, name, 'Java', 'Build' if package in ('Maven', 'Gradle') else 'Library', 'Uncommon', '🦋', pattern,
            f'Caused by: {name}: example diagnostic', label=label, priority=100, source=source)
        entries[-1].update(package=package, verification='documented-exception')
    if library_path.exists():
        roots = {e['name']: e for e in entries if e['family_id'] == e['id'] and e['language'] == 'Python'}
        for number, exception in ((500, 'Exception'), (501, 'FloatingPointError'), (502, 'LookupError'), (503, 'ReferenceError'), (504, 'UnicodeError')):
            add(number, exception, 'Python', 'Runtime', 'Common', '🐞', py(exception), f'{exception}: unspecified')
        roots = {e['name']: e for e in entries if e['family_id'] == e['id'] and e['language'] == 'Python'}
        for item in json.loads(library_path.read_text(encoding='utf-8')):
            if item.get('retired'):
                continue
            exception, message, number = item['exception'], item['template'], item['id']
            chunks = message.split('\u0000')
            # Escape whitespace separately: re.escape(' ') produces a backslash-space.
            pattern = r'[^\n]*?'.join(''.join(r'\s+' if part.isspace() else re.escape(part)
                                             for part in re.split(r'(\s+)', chunk)) for chunk in chunks)
            context = r'File "[^"\n]*(?:/|\\)' + re.escape(item['module']) + r'(?:/|\\)[^"\n]*", line \d+'
            sample_message = message.replace('\u0000', 'sample_value')
            sample = f'Traceback (most recent call last):\n  File "/venv/site-packages/{item["module"]}/example.py", line 12, in run\n{exception}: {sample_message}'
            parent = roots.get(exception)
            add(number, f'{item["package"]}.{exception}.{item["key"][:12]}', 'Python', 'Library', 'Uncommon', '🦋',
                py(exception) + r'[ \t]*' + pattern + r'[ \t]*$', sample,
                family=parent['id'] if parent else None,
                label=message.replace('\u0000', '…'), priority=200 + min(len(''.join(chunks)), 500), source=item['source'])
            entries[-1].update(package=item['package'], context=context, exception=exception,
                               verification='source-template', template_key=item['key'], message_template=message)

    assert len({e['id'] for e in entries}) == len(entries)
    assert len({(e['language'], e['name']) for e in entries}) == len(entries)
    numbers = {e['id'] for e in entries}
    for entry in entries:
        re.compile(entry['pattern'], re.I | re.M)
        assert entry['family_id'] in numbers
    return sorted(entries, key=lambda e: e['id'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    entries = catalog()
    data = json.dumps(entries, ensure_ascii=False, indent=2) + '\n'
    for path in (ROOT / 'server/errors.json', ROOT / 'extension/errors.json'):
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != data:
                parser.error(f'Catalog is out of sync: {path}')
        else:
            path.write_text(data, encoding='utf-8')
    detectors = (ROOT / 'server/diagnostics.json').read_text(encoding='utf-8')
    detector_path = ROOT / 'extension/diagnostics.json'
    if args.check:
        if not detector_path.exists() or detector_path.read_text(encoding='utf-8') != detectors:
            parser.error('Shared diagnostic detectors are out of sync')
    else:
        detector_path.write_text(detectors, encoding='utf-8')
    notices = '\n\n'.join(path.read_text(encoding='utf-8') for path in sorted((ROOT / 'docs/catalog-licenses').glob('*.txt')))
    notice_path = ROOT / 'extension/THIRD_PARTY_NOTICES.txt'
    if args.check:
        if not notice_path.exists() or notice_path.read_text(encoding='utf-8') != notices:
            parser.error('Third-party notices are out of sync')
    else:
        notice_path.write_text(notices, encoding='utf-8')
    counts = {lang: sum(e['language'] == lang for e in entries) for lang in ('C', 'Python', 'Java')}
    print(f'{len(entries)} diagnostic entries: {counts}')


if __name__ == '__main__':
    main()
