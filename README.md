# AI Tools

## Native Deep Agents (Agentic)

The app uses a single universal workflow:

1. One input workspace in the UI.
2. Deep Agent receives all skills from `skills/*/SKILL.md`.
3. `AGENTS.md` is loaded as global memory.
4. A soft nudge (`--nudge`, app context) selects expected output schema.
5. The agent decides which skill/tool to use.
6. Deep Agents backend is explicitly `FilesystemBackend(root_dir=<project>)`.
7. Runtime injects an explicit task nudge prompt from `config.yaml -> agentic_routing.nudge_prompts`.

## Shared Output Schemas (minimal)

1. `SingleText` -> `text`
2. `TextPair` -> `corrected`, `rewritten`
3. `Alternatives` -> `alternatives[]` where item is `value`, `explanation`

## Run from command line

```bash
./scripts/run_app.sh --text "Explain CAP theorem"
./scripts/run_app.sh --nudge slack --app slack --text "hi team pls review by tomrw"
./scripts/run_app.sh --nudge commands --text "list large files in current directory"
```

Legacy flags remain accepted for compatibility:

```bash
./scripts/run_app.sh --tab Proofread --app slack --text "quick draft message"
```

## Refresh models

Use `Refresh Models` button in the GUI.

Refresh runs only through `skills/refresh-llms/scripts/refresh_llms.sh` via runtime action `refresh_models`.

## Window placement

When `--window-x/--window-y` are missing, the app starts centered in the visible desktop bounds.

## Validation / test script

Run the full local validation pipeline:

```bash
./scripts/test_app.sh
```

It runs:
1. `ruff check`
2. `compileall`
3. `pytest`

## Dead code audit (current)

This refactor removed obsolete paths:
1. Deterministic tab/app skill routing path.
2. Resolved payload blob and synthetic “execute skill with payload” prompt path.
3. Unused `preview_instruction` runtime API.
4. Unused deterministic `RouteError` export.
5. Unused `commands` config section in settings model.
