
19: - Added deterministic max-events boundary tests (zero, equal boundary) to ensure behavior is consistent.
- Added deterministic invoke_streamed max-events boundary tests for first-event success, zero-event failure, and equal-boundary behavior with diagnostics callbacks.
- GUI _run_action now bridges invoke_streamed diagnostics through root.after(0, ...) so worker threads never touch widgets directly.
- Final streamed structured output is rebuilt into AgentResponse before scheduling _display_result on the main thread.
- GUI SkillExecutionError failure paths now keep streamed diagnostics visible while scheduling error/status/busy-state updates exclusively through root.after(0, ...).
- Timeout and max-events GUI failures set explicit failed status text instead of wiping diagnostics state.
