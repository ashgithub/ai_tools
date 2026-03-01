# AI Tools

## Deep Agents Skill Runtime

The app now uses a skill-driven runtime:

1. Global memory and behavior rules are in `AGENTS.md`.
2. Capabilities are implemented as skills under `skills/<skill-id>/SKILL.md`.
3. Skills are auto-discovered at startup from the `skills/` directory.
4. UI routing is deterministic (tab/app context -> skill id) and fail-fast.
5. Model refresh is executed only via the `refresh-llms` skill script.

Run from command line with:

```bash
./scripts/run_app.sh --tab "Q&A" --text "What is LangGraph?"
```

## Multi-monitor window placement

The GUI client (`clients/multi_tool_client.py`) supports optional window placement flags:

- `--window-x`: window x coordinate
- `--window-y`: window y coordinate
- `--window-width`: window width (default `900`)
- `--window-height`: window height (default `800`)

When `--window-x` and `--window-y` are provided, the client clamps the final position
to visible virtual desktop bounds so the window is not placed off-screen.

### Hammerspoon default monitor strategy

`init.lua` now computes window coordinates before launching Python with this deterministic order:

1. Frontmost application's focused window screen
2. Mouse cursor screen (fallback)
3. Primary screen (final fallback)

The window is centered on the selected screen's visible frame and clamped to stay fully visible.

## Toolkit alternatives

Current recommendation: stay on `tkinter` with launcher-driven placement for the lowest-risk fix.

Possible migration targets:

- `PySide6`: strongest desktop APIs and monitor handling, but heavier dependency and larger rewrite.
- `wxPython`: native-style widgets and solid monitor support, with a smaller ecosystem than Qt.

## OCI model cache

The app now loads model names from a strict OCI-backed cache flow.

Configure this in `config.yaml`:

```yaml
model_cache:
  enabled: true
  directory: ".cache"
  filename: "oci_models_cache.json"
  refresh_hours: 24
```

Behavior:

1. If cache is fresh, use it.
2. If cache is stale, click `Refresh Models` next to the model selector to execute the `refresh-llms` skill.
3. If cache is missing or invalid, use the `Refresh Models` button before using text tools.
4. If refresh fails, the app exits non-zero and shows an error.

Default model selection uses a single source: `oci.default_model` in `config.yaml`.
The cache JSON stores model metadata only and does not persist a `default_model`.

## Standalone OCI list_models test

Run:

```bash
uv run clients/test_oci_list_models.py
```

What success looks like:

1. `OCI list_models success`
2. Header lines for profile/endpoint/compartment.
3. One line per model: `id | display_name | vendor | lifecycle_state`.

If it fails, check:

1. OCI profile name in `config.yaml` (`oci.profile`) and `~/.oci/config`.
2. Compartment OCID in `config.yaml` (`oci.compartment`).
3. Service endpoint region in `config.yaml` (`oci.service_endpoint`).
4. IAM policy/dynamic-group scope for `generative_ai` `list_models`.
