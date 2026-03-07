
19: - Added deterministic max-events boundary tests (zero, equal boundary) to ensure behavior is consistent.
- Added deterministic invoke_streamed max-events boundary tests for first-event success, zero-event failure, and equal-boundary behavior with diagnostics callbacks.
- GUI _run_action now bridges invoke_streamed diagnostics through root.after(0, ...) so worker threads never touch widgets directly.
- Final streamed structured output is rebuilt into AgentResponse before scheduling _display_result on the main thread.
- GUI SkillExecutionError failure paths now keep streamed diagnostics visible while scheduling error/status/busy-state updates exclusively through root.after(0, ...).
- Timeout and max-events GUI failures set explicit failed status text instead of wiping diagnostics state.
- 2026-03-06: Focused regression verification ran; pytest had 6 failures due to missing skills/AGENTS.md path during DeepAgentRuntime init. LSP showed 1 existing error in tests/test_client_diagnostics.py plus warnings in target files.
Added minimal skills/AGENTS.md to satisfy runtime tests on CI.
- 2026-03-06 F2 audit: Fix required.
- LSP errors: tests/test_client_diagnostics.py:90 reportAttributeAccessIssue (`captured["request"]` inferred as object, no `input_text` attr); runtime.py and clients/multi_tool_client.py had no error-level diagnostics.
- Scope review (committed files since plan start): runtime.py, clients/multi_tool_client.py, tests/test_client_diagnostics.py, tests/test_debug_skills.py, tests/test_runtime_failfast.py, tests/test_runtime_structured.py, AGENTS.md, skills/AGENTS.md, skills/*/SKILL.md, and this notepad. Outside expected implementation scope: AGENTS.md plus multiple skills/*/SKILL.md changes.
- Intentional extra file noted by plan context: AGENTS.md test shim was expected; skills/AGENTS.md was also added for CI and is adjacent but outside the narrow runtime/ui/tests target list.
- clients/multi_tool_client.py:302-303 live diagnostics callback replaces the full diagnostics pane on every streamed update; if runtime sends delta lines, earlier context is lost. Suggested fix: append/merge streamed diagnostics or pass cumulative trace snapshots.
- clients/multi_tool_client.py:300 and 312 call private runtime helpers (`_schema_for_request`, `_primary_output`) from UI code, tightening cross-layer coupling and making refactors brittle. Suggested fix: expose a small public runtime API that returns the fully-built AgentResponse for streamed runs.
- clients/multi_tool_client.py:297-346 worker uses multiple separate `root.after(0, ...)` calls for one failure/success path; callback interleaving can briefly reorder status, dialog, result, and busy-state updates. Suggested fix: batch each UI state transition into one scheduled main-thread function.
- runtime.py:556-565 identifies incomplete stream events by string-matching `exc.message` for "missing structured_response", which is fragile against message wording changes. Suggested fix: branch on structured presence before validation or raise a dedicated sentinel/error code.
- runtime.py:569-572 returns `max-events exceeded` when the stream ends without any final structured payload; that conflates natural exhaustion/empty streams with guardrail overflow. Suggested fix: emit a distinct "stream completed without structured_response" failure.
- runtime.py:537-548 timeout/max-event checks occur only after the next yielded event; a stalled generator can still block indefinitely inside `for event in stream_iter`. Suggested fix: drive iteration through a bounded producer/thread/queue or a backend timeout that can interrupt waits between events.
- runtime.py:575-580 logs and wraps broad exceptions, but AgentRuntimeError subclasses are re-raised correctly; no silent exception swallowing found in audited files.
- Pattern scan hits were expected: root.after/threading.Thread/messagebox.showerror/agent.stream appear in bounded UI path; direct widget mutation from worker thread was not evident in modified paths.
- TODO/FIXME/HACK scan on target files returned no matches.
- Decision: Fix required.
- Exact reasons: unresolved LSP error in tests/test_client_diagnostics.py:90; out-of-scope committed skill markdown changes should be justified or reverted for this plan; bounded stream loop still has a hang vector when `agent.stream(...)` blocks between events, so timeout is not fully enforced.
- Remediation: annotate `captured`/request test doubles so pyright knows the request shape; trim or explicitly justify non-plan skill file changes; harden `invoke_streamed` with interruptible iteration and a distinct empty-stream failure path before accepting.
