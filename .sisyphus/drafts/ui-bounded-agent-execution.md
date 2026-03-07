# Draft: UI Bounded Agent Execution

## Requirements (confirmed)
- the ui version seems to go into an infite loop
- debug version seems to work ok
- fix it
- we do not want to change ui functionality

## Technical Decisions
- Investigate as a planning task only; no code changes in this session
- Treat root cause as unbounded deep-agent execution in UI path unless exploration disproves it

## Research Findings
- clients/multi_tool_client.py:_run_action uses runtime.invoke() in worker thread
- runtime.py:_execute_deep_agent uses blocking agent.invoke(payload)
- scripts/debug_skills.py uses create_agent(..., debug=True) and stream() with max-events cap

## Open Questions
- Should bounded execution use event-count limit only, timeout only, or both?
- Should UI diagnostics update live during streaming, or only after completion/failure?
- Should debug=True be enabled for UI-created agents or remain debug-script-only?

## Scope Boundaries
- INCLUDE: runtime/UI changes to prevent unbounded hangs, diagnostics/error handling, tests
- EXCLUDE: changing user-visible UI features or redesigning skills architecture
