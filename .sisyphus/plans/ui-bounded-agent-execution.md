# UI Bounded Agent Execution

## TL;DR
> **Summary**: Replace the GUI's unbounded deep-agent `invoke()` path with a bounded stream-based execution path that uses `debug=True`, enforces both timeout and max-event limits, emits live diagnostics safely to the UI, and preserves existing result rendering semantics.
> **Deliverables**:
> - bounded runtime streaming path for deep-agent execution
> - GUI integration with live diagnostics updates and fail-fast timeout/cap handling
> - automated tests for runtime bounded execution and GUI diagnostics/status behavior
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: runtime bounded stream helper → GUI worker integration → runtime/client tests

## Context
### Original Request
User reported that the debug version works, but the UI version appears to enter an infinite loop. They asked to fix it without changing UI functionality.

### Interview Summary
Confirmed decisions:
- Guardrail strategy: **Timeout + Events**
- Diagnostics behavior: **Live Updates**
- UI deep-agent creation: **debug=True**

Confirmed constraints:
- Preserve existing UI functionality and render behavior
- Treat the issue as a deep-agent execution hang, not a Tkinter recursion issue

### Metis Review (gaps addressed)
Metis identified the critical guardrails that shape this plan:
- Do **not** fall back to unbounded `agent.invoke()` in the UI bounded path
- Preserve `render_kind`-driven final rendering behavior in `clients/multi_tool_client.py`
- Keep all UI mutations on the main Tk thread via `root.after(...)`
- Reuse stream/event normalization patterns from `scripts/debug_skills.py`
- Add explicit automated coverage for bounded success, timeout, max-events, and live diagnostics updates

## Work Objectives
### Core Objective
Eliminate the UI hang by replacing the current unbounded deep-agent execution path with a bounded, stream-based runtime path that fails fast on timeout or event-cap exhaustion while preserving successful output behavior.

### Deliverables
- A new bounded deep-agent execution path in `src/ai_tools/agent_runtime/runtime.py`
- GUI worker integration in `clients/multi_tool_client.py` that consumes bounded execution updates and renders diagnostics live
- Automated tests covering runtime bounded execution success/failure and GUI diagnostics/status updates

### Definition of Done (verifiable conditions with commands)
- The UI execution path no longer relies on unbounded `agent.invoke()` for normal deep-agent runs.
- Successful runs still produce the same `structured_output`, `primary_output`, and `render_kind` semantics as before.
- Timeout exhaustion raises a fail-fast `SKILL_EXECUTION_FAILED` instead of hanging.
- Max-event exhaustion raises a fail-fast `SKILL_EXECUTION_FAILED` instead of hanging.
- Diagnostics can be updated incrementally during execution without violating Tkinter thread-safety.
- Commands:
  - `uv run pytest -q tests/test_runtime_structured.py`
  - `uv run pytest -q tests/test_runtime_failfast.py`
  - `uv run pytest -q tests/test_client_diagnostics.py`
  - `uv run pytest -q tests/test_debug_skills.py`

### Must Have
- Use `create_agent(..., debug=True)` for the UI bounded path
- Enforce **both** timeout and max-events
- Preserve final UI rendering semantics for `alternatives`, `text_pair`, and `single_text`
- Emit live diagnostics updates through `root.after(...)`
- No unbounded `invoke()` fallback in the UI bounded path

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Must NOT redesign skills architecture or change skill instructions in this fix
- Must NOT alter `Copy Output`, `Done`, or tab rendering semantics
- Must NOT change refresh-model behavior unless strictly needed for shared runtime signatures
- Must NOT require manual testing to verify correctness
- Must NOT update widgets directly from worker threads

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after + pytest
- QA policy: Every task includes agent-executed scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: runtime bounded execution foundation, event/trace helpers, error policy, runtime tests
Wave 2: GUI worker integration, live diagnostics updates, client tests, regression verification

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2, 3, 4, 5, 6
- Task 2 blocks Tasks 6, 7
- Task 3 blocks Tasks 6, 7
- Task 4 blocks Task 7
- Task 5 blocks Task 8
- Task 6 blocks Task 8
- Task 7 blocks Task 8
- Task 8 blocks Final Verification Wave

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → runtime, diagnostics helpers, runtime tests
- Wave 2 → 3 tasks → GUI integration, client tests, regression verification

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Add bounded deep-agent execution contract in runtime

  **What to do**: Introduce a dedicated bounded execution path in `src/ai_tools/agent_runtime/runtime.py` for normal deep-agent runs. This path must create the agent with `debug=True`, consume `agent.stream(...)` instead of relying on plain `agent.invoke(...)`, accept explicit `timeout_seconds` and `max_events` inputs, and return the same final structured result contract used by `DeepAgentRuntime.invoke()`. Use `scripts/debug_skills.py` streaming structure as the reference pattern, but do not copy its unbounded `invoke()` fallback.
  **Must NOT do**: Do not remove or alter refresh-model execution. Do not redesign `AgentResponse`. Do not silently fall back to unbounded `agent.invoke()` if streaming fails or stalls.

  **Recommended Agent Profile**:
  - Category: `backend-runtime` — Reason: this is the core execution-path change.
  - Skills: [`python`, `testing`] — needed for runtime refactor and pytest updates.
  - Omitted: [`ui`] — no GUI widget logic should be changed in this task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 3, 4, 5, 6] | Blocked By: []

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/ai_tools/agent_runtime/runtime.py` — current `DeepAgentRuntime.invoke()`, `_execute_deep_agent()`, `_extract_structured_response()`, `_primary_output()` behavior must be preserved for successful runs.
  - Pattern: `scripts/debug_skills.py` — `main()`, `_normalize_stream_event()`, `_event_payload()`, and stream loop around lines 387-453 provide the existing in-repo bounded-stream pattern.
  - Pattern: `src/ai_tools/agent_runtime/runtime.py` — `_trace_lines_for_result()` and `_trace_message_lines()` define the current trace-line format that downstream diagnostics expect.
  - API/Type: `src/ai_tools/agent_runtime/types.py:AgentRequest` — request contract for input, app context, options, model.
  - API/Type: `src/ai_tools/agent_runtime/types.py:AgentResponse` — final response contract that must remain stable.
  - Test: `tests/test_runtime_structured.py` — current success-path assertions and fake-agent mocking style.
  - External: deepagents stream API used in `scripts/debug_skills.py` — use `agent.stream(payload, stream_mode="values")`, falling back only to alternate stream signature if needed, not to invoke.

  **Acceptance Criteria** (agent-executable only):
  - [x] `DeepAgentRuntime.invoke()` no longer depends on unbounded `agent.invoke()` for normal non-refresh UI-oriented deep-agent runs.
  - [x] A bounded execution helper exists that accepts timeout and max-event controls and produces validated structured output using existing schema validation.
  - [x] Successful bounded runs still yield the same `render_kind`, `structured_output`, and `primary_output` semantics as the current runtime path.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Runtime bounded execution succeeds with streamed final event
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_structured.py -k bounded_stream_success
    Expected: Targeted test passes and proves streamed final result is converted into valid AgentResponse data.
    Evidence: .sisyphus/evidence/task-1-runtime-bounded-success.txt

  Scenario: Runtime does not fall back to unbounded invoke on stream issues
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_failfast.py -k no_invoke_fallback
    Expected: Targeted test passes and asserts bounded path fails fast without calling unbounded invoke.
    Evidence: .sisyphus/evidence/task-1-runtime-no-fallback.txt
  ```

  **Commit**: YES | Message: `fix(runtime): add bounded deep-agent stream execution` | Files: [`src/ai_tools/agent_runtime/runtime.py`, `tests/test_runtime_structured.py`, `tests/test_runtime_failfast.py`]

- [x] 2. Add runtime event normalization and diagnostics callback support

  **What to do**: Add runtime-internal helpers needed to convert streamed events into diagnostics lines suitable for the GUI. Reuse compact line-oriented trace behavior from runtime and normalization ideas from `debug_skills.py`. Add a callback hook or equivalent bounded-execution reporting mechanism so callers can receive incremental diagnostics safely without changing final response semantics.
  **Must NOT do**: Do not expose raw event dicts directly to the GUI if compact trace lines are sufficient. Do not make diagnostics dependent on the debug script module.

  **Recommended Agent Profile**:
  - Category: `backend-runtime` — Reason: helper extraction and callback design belong in runtime.
  - Skills: [`python`] — helper and callback wiring.
  - Omitted: [`ui`] — UI consumption happens later.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6, 7] | Blocked By: [1]

  **References**:
  - Pattern: `scripts/debug_skills.py` — `_normalize_stream_event()`, `_event_payload()`, `_extract_tool_calls()` for stream event inspection patterns.
  - Pattern: `src/ai_tools/agent_runtime/runtime.py` — existing trace format from `_trace_lines_for_result()` must remain the diagnostics style baseline.
  - Pattern: `clients/multi_tool_client.py:format_diagnostics_trace` — diagnostics pane already expects `list[str]` joined into display text.
  - Test: `tests/test_debug_skills.py` — existing helper-test style for normalized events.
  - Test: `tests/test_client_diagnostics.py` — diagnostics formatting coverage should expand here or in a new client-focused test file.

  **Acceptance Criteria**:
  - [x] Runtime exposes an incremental diagnostics mechanism compatible with line-oriented GUI rendering.
  - [x] Streamed event normalization does not change the final trace format expected by current diagnostics display.
  - [x] Diagnostics updates can be consumed independently of final completion.

  **QA Scenarios**:
  ```
  Scenario: Runtime emits line-oriented diagnostics for streamed events
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_structured.py -k stream_diagnostics_lines
    Expected: Targeted test passes and confirms streamed events become compact trace lines.
    Evidence: .sisyphus/evidence/task-2-runtime-diagnostics.txt

  Scenario: Event normalization handles deepagents stream tuples and plain payloads
    Tool: Bash
    Steps: uv run pytest -q tests/test_debug_skills.py -k "normalize or event"
    Expected: Targeted tests pass, proving normalization assumptions remain valid.
    Evidence: .sisyphus/evidence/task-2-event-normalization.txt
  ```

  **Commit**: YES | Message: `fix(runtime): add stream diagnostics callbacks` | Files: [`src/ai_tools/agent_runtime/runtime.py`, `tests/test_runtime_structured.py`, `tests/test_debug_skills.py`, `tests/test_client_diagnostics.py`]

- [x] 3. Enforce timeout fail-fast in bounded runtime path

  **What to do**: Add explicit wall-clock timeout enforcement inside the bounded stream-consumption loop. When elapsed time exceeds the configured/default timeout, abort the run and raise `SkillExecutionError` with `code="SKILL_EXECUTION_FAILED"` and a message that clearly states timeout exhaustion. Ensure partial stream progress does not convert into a successful result unless a complete valid final result policy is explicitly satisfied by the implementation.
  **Must NOT do**: Do not let timeout merely update status text; it must terminate the execution path. Do not require manual cancellation.

  **Recommended Agent Profile**:
  - Category: `backend-runtime` — Reason: timeout policy is part of execution control.
  - Skills: [`python`, `testing`] — runtime behavior plus failure-path tests.
  - Omitted: [`ui`] — status wiring belongs later.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6, 7] | Blocked By: [1]

  **References**:
  - Pattern: `src/ai_tools/agent_runtime/runtime.py` — existing `SkillExecutionError` wrapping and error-code conventions.
  - Pattern: `tests/test_runtime_failfast.py` — fail-fast testing style and current error assertions.
  - Metis Guardrail: timeout failure must be agent-executable and must not preserve the original hang vector.

  **Acceptance Criteria**:
  - [x] Bounded runtime execution raises `SKILL_EXECUTION_FAILED` when timeout is exceeded.
  - [x] Timeout failure happens without invoking unbounded fallback code.
  - [x] Error text is specific enough for the GUI to surface a meaningful failure message.

  **QA Scenarios**:
  ```
  Scenario: Runtime fails fast on timeout exhaustion
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_failfast.py -k timeout
    Expected: Targeted test passes and asserts SKILL_EXECUTION_FAILED with timeout-related message.
    Evidence: .sisyphus/evidence/task-3-timeout-failfast.txt

  Scenario: Successful bounded path is unaffected by timeout logic
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_structured.py -k bounded_stream_success
    Expected: Success-path test still passes after timeout enforcement is added.
    Evidence: .sisyphus/evidence/task-3-timeout-regression.txt
  ```

  **Commit**: YES | Message: `fix(runtime): fail fast on agent timeout` | Files: [`src/ai_tools/agent_runtime/runtime.py`, `tests/test_runtime_failfast.py`, `tests/test_runtime_structured.py`]

- [x] 4. Enforce max-event fail-fast in bounded runtime path

  **What to do**: Add explicit max-event enforcement to the bounded stream loop. If the stream produces more events than allowed, terminate the run and raise `SkillExecutionError` with a max-events/cap-exceeded message. Match the event-counting model used by `scripts/debug_skills.py`, but adapt it for production runtime behavior rather than debug reporting.
  **Must NOT do**: Do not silently truncate and then return success unless a complete validated final result has already been established by the implementation. Do not leave the GUI waiting after the cap is reached.

  **Recommended Agent Profile**:
  - Category: `backend-runtime` — Reason: execution bound enforcement is runtime logic.
  - Skills: [`python`, `testing`] — runtime logic and fail-fast tests.
  - Omitted: [`ui`] — GUI wiring comes later.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [7] | Blocked By: [1]

  **References**:
  - Pattern: `scripts/debug_skills.py:396-420` — existing event-cap loop structure.
  - Pattern: `tests/test_runtime_failfast.py` — error-assertion structure.
  - Metis Guardrail: diagnostics flood should be bounded and must not freeze the UI.

  **Acceptance Criteria**:
  - [x] Bounded runtime execution raises `SKILL_EXECUTION_FAILED` when max-events is exceeded.
  - [x] Event counting is deterministic and test-covered.
  - [x] Max-event failure does not call unbounded invoke or hang the caller.

  **QA Scenarios**:
  ```
  Scenario: Runtime fails fast when event cap is exceeded
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_failfast.py -k max_events
    Expected: Targeted test passes and asserts SKILL_EXECUTION_FAILED with max-events-related message.
    Evidence: .sisyphus/evidence/task-4-max-events-failfast.txt

  Scenario: Stream diagnostics remain bounded under event-cap enforcement
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_structured.py -k stream_diagnostics_lines
    Expected: Diagnostics test still passes with event-cap logic active.
    Evidence: .sisyphus/evidence/task-4-max-events-diagnostics.txt
  ```

  **Commit**: YES | Message: `fix(runtime): enforce max events for agent streams` | Files: [`src/ai_tools/agent_runtime/runtime.py`, `tests/test_runtime_failfast.py`, `tests/test_runtime_structured.py`]

- [x] 5. Preserve final result extraction and render semantics under streamed execution

  **What to do**: Ensure the bounded streamed path still uses the current schema-validation, structured-output extraction, and primary-output selection behavior already defined in runtime. The final successful response contract must remain compatible with all existing GUI render branches. Update tests so streamed success proves parity with the prior invoke-based success semantics.
  **Must NOT do**: Do not change `render_kind` mappings, output field selection rules, or the GUI’s expectations for `alternatives`, `text_pair`, or `single_text`.

  **Recommended Agent Profile**:
  - Category: `backend-runtime` — Reason: preserves stable response contract under new transport.
  - Skills: [`python`, `testing`] — parity validation.
  - Omitted: [`ui`] — rendering remains unchanged in this task.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [8] | Blocked By: [1]

  **References**:
  - Pattern: `src/ai_tools/agent_runtime/runtime.py:_extract_structured_response` — schema validation contract.
  - Pattern: `src/ai_tools/agent_runtime/runtime.py:_primary_output` — output selection rules.
  - Pattern: `clients/multi_tool_client.py:_display_result` — render behavior that must remain unchanged.
  - Test: `tests/test_runtime_structured.py` — extend current success assertions to streamed execution.

  **Acceptance Criteria**:
  - [x] Streamed success produces a valid `AgentResponse` identical in core semantics to the old success path.
  - [x] Existing GUI render branches can consume the streamed success output without modification to their data assumptions.
  - [x] Regression tests prove unchanged `primary_output` and `render_kind` for representative requests.

  **QA Scenarios**:
  ```
  Scenario: Streamed success preserves text-pair and single-text semantics
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_structured.py -k "stream and render"
    Expected: Targeted tests pass and assert unchanged render_kind/primary_output behavior.
    Evidence: .sisyphus/evidence/task-5-streamed-render-semantics.txt

  Scenario: Existing structured runtime tests continue to pass under streamed path
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_structured.py
    Expected: Full runtime structured test file passes.
    Evidence: .sisyphus/evidence/task-5-runtime-structured-full.txt
  ```

  **Commit**: YES | Message: `test(runtime): verify streamed response parity` | Files: [`tests/test_runtime_structured.py`, `src/ai_tools/agent_runtime/runtime.py`]

- [x] 6. Wire GUI worker to bounded runtime path with live diagnostics updates

  **What to do**: Update `clients/multi_tool_client.py` so `_run_action()` uses the new bounded runtime execution path instead of the old opaque blocking path. Feed incremental diagnostics from the worker to the Diagnostics tab using `root.after(...)` only, keep the initial queued trace, preserve busy-state handling, and continue rendering the final result through `_display_result(response)` once the bounded runtime returns success.
  **Must NOT do**: Do not update Tk widgets directly inside the worker thread. Do not alter button layout, shortcut behavior, or final result rendering logic.

  **Recommended Agent Profile**:
  - Category: `desktop-ui` — Reason: Tkinter worker orchestration and thread-safe updates.
  - Skills: [`python`, `tkinter`, `testing`] — UI worker thread safety and testability.
  - Omitted: [`backend-runtime`] — runtime helper must already exist before wiring.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [8] | Blocked By: [1, 2, 3]

  **References**:
  - Pattern: `clients/multi_tool_client.py:_run_action` — current worker-thread structure and busy-state handling.
  - Pattern: `clients/multi_tool_client.py:_render_diagnostics` — current diagnostics rendering entrypoint.
  - Pattern: `clients/multi_tool_client.py:_display_result` — final rendering must remain the same.
  - Pattern: `scripts/debug_skills.py` — stream iteration and incremental event handling ideas.
  - Metis Guardrail: all UI updates must flow through `root.after(...)`.

  **Acceptance Criteria**:
  - [x] GUI worker uses bounded runtime execution and no longer waits on the legacy unbounded deep-agent path.
  - [x] Diagnostics tab can update during execution without thread-safety violations.
  - [x] Final success still routes through `_display_result(response)` and preserves visible UI behavior.

  **QA Scenarios**:
  ```
  Scenario: GUI worker schedules live diagnostics updates safely
    Tool: Bash
    Steps: uv run pytest -q tests/test_client_diagnostics.py -k live
    Expected: Targeted test passes and proves diagnostics updates are scheduled via UI-safe callback flow.
    Evidence: .sisyphus/evidence/task-6-gui-live-diagnostics.txt

  Scenario: GUI success path still displays final response after bounded execution
    Tool: Bash
    Steps: uv run pytest -q tests/test_client_diagnostics.py -k final_result
    Expected: Targeted test passes and confirms final response rendering callback still runs after bounded execution completes.
    Evidence: .sisyphus/evidence/task-6-gui-final-result.txt
  ```

  **Commit**: YES | Message: `fix(ui): use bounded streamed agent execution` | Files: [`clients/multi_tool_client.py`, `tests/test_client_diagnostics.py`]

- [x] 7. Add GUI failure-path handling for timeout and max-events exhaustion

  **What to do**: Update GUI error/status behavior so timeout and max-event failures surface as explicit errors through the existing messagebox/status flow, while still releasing busy state and leaving diagnostics visible for troubleshooting. Add automated tests for timeout/cap failure messaging and state reset behavior.
  **Must NOT do**: Do not swallow runtime exceptions. Do not leave the UI disabled after failure.

  **Recommended Agent Profile**:
  - Category: `desktop-ui` — Reason: user-facing failure handling in Tkinter worker callbacks.
  - Skills: [`python`, `tkinter`, `testing`] — failure wiring and GUI callback assertions.
  - Omitted: [`backend-runtime`] — runtime failure generation should already exist.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [8] | Blocked By: [2, 3, 4]

  **References**:
  - Pattern: `clients/multi_tool_client.py:_run_action` — current exception branches and busy-state reset.
  - Pattern: `src/ai_tools/agent_runtime/errors.py` — error code/message conventions used by GUI.
  - Test: `tests/test_runtime_failfast.py` — expected runtime failure contracts.
  - Test: `tests/test_client_diagnostics.py` — extend with GUI status/error assertions.

  **Acceptance Criteria**:
  - [x] Timeout and max-event failures surface as user-visible errors through existing error channels.
  - [x] Busy state is cleared after failure.
  - [x] Diagnostics content remains available after failure for debugging.

  **QA Scenarios**:
  ```
  Scenario: GUI reports timeout failure and clears busy state
    Tool: Bash
    Steps: uv run pytest -q tests/test_client_diagnostics.py -k timeout
    Expected: Targeted test passes and asserts error/status handling plus busy-state reset.
    Evidence: .sisyphus/evidence/task-7-gui-timeout.txt

  Scenario: GUI reports max-events failure and preserves diagnostics
    Tool: Bash
    Steps: uv run pytest -q tests/test_client_diagnostics.py -k max_events
    Expected: Targeted test passes and confirms diagnostics remain inspectable after cap failure.
    Evidence: .sisyphus/evidence/task-7-gui-max-events.txt
  ```

  **Commit**: YES | Message: `fix(ui): surface bounded execution failures` | Files: [`clients/multi_tool_client.py`, `tests/test_client_diagnostics.py`]

- [x] 8. Run focused regression suite and confirm no UI behavior drift

  **What to do**: Execute and, if needed, finalize tests proving the bounded streamed path fixes the hang without changing normal UI semantics. Ensure runtime, fail-fast, debug-helper, and client diagnostics suites all pass together. If test names introduced in earlier tasks differ, update this task’s commands to the final actual test selectors before completion.
  **Must NOT do**: Do not rely on manual GUI clicks. Do not skip any targeted suite introduced by earlier tasks.

  **Recommended Agent Profile**:
  - Category: `qa-verification` — Reason: final automated regression verification.
  - Skills: [`pytest`] — focused suite execution and evidence collection.
  - Omitted: [`implementation`] — this task verifies, not designs.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [Final Verification Wave] | Blocked By: [5, 6, 7]

  **References**:
  - Test: `tests/test_runtime_structured.py`
  - Test: `tests/test_runtime_failfast.py`
  - Test: `tests/test_client_diagnostics.py`
  - Test: `tests/test_debug_skills.py`
  - Metis Guardrail: acceptance criteria must be concrete pytest commands, not manual QA.

  **Acceptance Criteria**:
  - [x] Focused runtime, fail-fast, debug-helper, and client-diagnostics suites all pass.
  - [x] Added bounded-execution tests are included in the passing run.
  - [x] No verification step requires human intervention.

  **QA Scenarios**:
  ```
  Scenario: Focused bounded-execution regression suite passes
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_structured.py tests/test_runtime_failfast.py tests/test_client_diagnostics.py tests/test_debug_skills.py
    Expected: Command exits 0 and all targeted tests pass.
    Evidence: .sisyphus/evidence/task-8-focused-regression.txt

  Scenario: Runtime and GUI failure-path selectors pass independently
    Tool: Bash
    Steps: uv run pytest -q tests/test_runtime_failfast.py tests/test_client_diagnostics.py
    Expected: Command exits 0, proving both runtime and GUI failure handling are covered.
    Evidence: .sisyphus/evidence/task-8-failure-regression.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: [`tests/test_runtime_structured.py`, `tests/test_runtime_failfast.py`, `tests/test_client_diagnostics.py`, `tests/test_debug_skills.py`, `clients/multi_tool_client.py`, `src/ai_tools/agent_runtime/runtime.py`]

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit after Task 1 to establish bounded runtime foundation
- Commit after Task 2 if helper/callback extraction is substantial
- Commit after Tasks 3-4 for explicit fail-fast guardrails
- Commit after Task 6 for GUI integration
- Do not squash verification-only evidence work into unrelated commits

## Success Criteria
- UI no longer appears to hang because deep-agent execution is bounded by timeout and max-events
- GUI receives live diagnostics during execution without thread-safety violations
- Successful outputs preserve prior semantics and render correctly
- Timeout/max-events failures are explicit, fast, and test-covered
- No path in the UI fix reintroduces unbounded `agent.invoke()` fallback
