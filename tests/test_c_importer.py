from scripts.import_c_catalog import gcc_calls, clang_definitions, cppcheck_calls, linker_calls, runtime_calls


def test_gcc_ast_reads_errors_and_normalizes_format_arguments():
    source = '''void run() { error_at(loc, "invalid operands to %<%s%> for %qT", op, type); warning_at(loc, 0, "a warning"); const char *docs = "error(\\\"not executable\\\")"; }'''
    assert gcc_calls(source)[0][0] == "invalid operands to '\x00' for '\x00'"
    assert len(gcc_calls(source)) == 1
    assert gcc_calls('void c_parser_objc_method() { error("expected class name"); }') == []
    assert gcc_calls('void run() { if (c_dialect_objc()) error("expected Objective-C name"); }') == []
    assert gcc_calls('void run() { error(dynamicMessage()); }') == []


def test_clang_excludes_warnings_cpp_and_unsupported_formatters():
    source = '''def err_utf8 : Error<"source file is not valid UTF-8">;
    def warning : Warning<"warning text">;
    def err_raw_string : Error<"raw string delimiter is too long">;
    def err_opencl : Error<"OpenCL type requires a feature">;
    def err_choice : Error<"invalid digit '%0' in %select{decimal|octal}1 constant">;
    def err_diff : Error<"unsupported %diff{a|b}0,1 formatting">;'''
    assert [item[0] for item in clang_definitions(source)] == ['err_utf8', 'err_choice']
    assert clang_definitions('def err_cpp : Error<"unexpected template declaration">;', parser=True) == []


def test_static_analysis_uses_reported_ids_and_error_severity():
    source = '''void run() { reportError(tok, Severity::error, "nullPointer", "Null pointer dereference"); reportError(tok, Severity::warning, "warningId", "Potential problem"); reportError(tok, Severity::error, "coutCerrMisusage", "bad output"); }'''
    assert [item[0] for item in cppcheck_calls(source)] == ['nullPointer']


def test_linker_streams_keep_dynamic_values_and_ignore_warnings():
    source = '''void run() { Err(ctx) << filename << ": unknown file type"; Warn(ctx) << "not an error"; Err(ctx) << "cannot open input file " << filename << ": " << why; }'''
    assert [item[0] for item in linker_calls(source)] == ['\x00: unknown file type', 'cannot open input file \x00: \x00']


def test_runtime_excludes_cpp_only_handlers_and_notes():
    source = '''void ErrorCallocOverflow::Print() { Report("ERROR: AddressSanitizer: calloc parameters overflow: %zu * %zu\\n", count, size); }
    void ErrorNewDeleteTypeMismatch::Print() { Report("ERROR: AddressSanitizer: C++ only allocation mismatch\\n"); }'''
    assert len(runtime_calls(source, True)) == 1
    source = '''void handleAlignment() { Diag(loc, DL_Error, ET, "assumption of %0 byte alignment failed"); Diag(loc, DL_Note, ET, "details here"); }'''
    assert runtime_calls(source, False)[0][0] == 'assumption of \x00 byte alignment failed'
