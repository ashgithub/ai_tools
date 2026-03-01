"""Prompt-building utilities for YAML-driven template rendering."""

from __future__ import annotations

from ai_tools.utils.config import get_settings


REWRITE_ALLOWED_START = "[[REWRITE_ALLOWED]]"
REWRITE_ALLOWED_END = "[[/REWRITE_ALLOWED]]"
REWRITE_FORBIDDEN_START = "[[REWRITE_FORBIDDEN]]"
REWRITE_FORBIDDEN_END = "[[/REWRITE_FORBIDDEN]]"


def _apply_placeholders(template: str, values: dict[str, str]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    return result


def _extract_block(text: str, start_tag: str, end_tag: str) -> str:
    start = text.find(start_tag)
    end = text.find(end_tag)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start + len(start_tag):end]


def _remove_block(text: str, start_tag: str, end_tag: str) -> str:
    start = text.find(start_tag)
    end = text.find(end_tag)
    if start == -1 or end == -1 or end < start:
        return text
    return text[:start] + text[end + len(end_tag):]


def _apply_rewrite_blocks(template: str, can_rewrite: bool) -> str:
    allowed_content = _extract_block(template, REWRITE_ALLOWED_START, REWRITE_ALLOWED_END)
    forbidden_content = _extract_block(template, REWRITE_FORBIDDEN_START, REWRITE_FORBIDDEN_END)

    result = template
    result = _remove_block(result, REWRITE_ALLOWED_START, REWRITE_ALLOWED_END)
    result = _remove_block(result, REWRITE_FORBIDDEN_START, REWRITE_FORBIDDEN_END)

    marker = "{rewrite_policy}"
    chosen = allowed_content if can_rewrite else forbidden_content
    if marker in result:
        result = result.replace(marker, chosen.strip())
    elif chosen.strip():
        result = result.rstrip() + "\n\n" + chosen.strip()
    return result


def _proofread_config() -> tuple[dict, dict]:
    settings = get_settings()
    proofread_cfg = settings.tab_prompts.get("Proofread", {})
    if not isinstance(proofread_cfg, dict):
        raise ValueError("Invalid config: tab_prompts.Proofread must be a mapping.")
    contexts = proofread_cfg.get("contexts", {})
    if not isinstance(contexts, dict):
        raise ValueError("Invalid config: tab_prompts.Proofread.contexts must be a mapping.")
    return proofread_cfg, contexts


def get_tab_template(
    tab_name: str,
    *,
    context_key: str = "general",
    can_rewrite: bool = False,
    os_value: str | None = None,
) -> str:
    """Return the active YAML-derived template with only relevant sections."""
    settings = get_settings()

    if tab_name == "Proofread":
        proofread_cfg, contexts = _proofread_config()
        template = proofread_cfg.get("template")
        if not isinstance(template, str) or not template.strip():
            raise ValueError(
                "Missing required config key: tab_prompts.Proofread.template in config.yaml"
            )
        context_value = str(contexts.get(context_key) or contexts.get("general") or "")
        expanded = _apply_placeholders(
            template,
            {
                "context": context_value,
                "input": "{input}",
                "rewrite_allowed": str(settings.prompts.rewrite_allowed),
                "rewrite_forbidden": str(settings.prompts.rewrite_forbidden),
                "output_instruction": str(settings.prompts.output_instruction),
            },
        )
        return _apply_rewrite_blocks(expanded, can_rewrite).strip()

    template = str(settings.tab_prompts.get(tab_name, ""))
    if tab_name == "Commands":
        active_os = os_value or (settings.commands.os_options[0] if settings.commands.os_options else "macos")
        return _apply_placeholders(template, {"os": active_os, "input": "{input}"}).strip()
    return _apply_placeholders(template, {"input": "{input}"}).strip()


def build_tab_prompt(tab_name: str, input_text: str, *, active_template: str) -> str:
    """Resolve the final prompt from the active template shown in UI."""
    return _apply_placeholders(active_template, {"input": input_text}).strip()
