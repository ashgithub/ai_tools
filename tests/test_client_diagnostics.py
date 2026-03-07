from clients.multi_tool_client import format_diagnostics_trace


def test_format_diagnostics_trace_with_lines():
    output = format_diagnostics_trace(["a", "b"])
    assert output == "a\nb"


def test_format_diagnostics_trace_empty():
    output = format_diagnostics_trace([])
    assert output == "No diagnostics captured for this run."
