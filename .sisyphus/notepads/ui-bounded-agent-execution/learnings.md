Plan: ui-bounded-agent-execution
Decisions:
- timeout + max-events
- live diagnostics
- debug=True for UI

Notes:
- Reuse debug_skills.py stream loop but do not fallback to invoke()
- Diagnostics must be line-oriented to match GUI
- All UI updates via root.after

- Added bounded invoke_streamed with per-event trace accumulation, strict no-invoke fallback, and timeout/max-events fail-fast behavior.
- Stream tests patch global memory validation because skills/AGENTS.md is absent in the current working tree; diagnostics remain line-oriented via existing runtime trace helpers.

- Runtime now exposes _event_payload, normalize_stream_event, normalize_and_trace_event, and stream_event_to_trace_lines; tuple events preserve explicit mode, plain payloads default to values, and diagnostics callbacks receive per-event line-oriented trace chunks.
