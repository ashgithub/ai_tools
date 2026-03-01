"""Deterministic tab/app routing for skill selection."""

from __future__ import annotations

from ai_tools.agent_runtime.errors import RouteError
from ai_tools.agent_runtime.types import AgentRequest


EMAIL_APPS = {
    "mail",
    "outlook",
    "thunderbird",
    "gmail",
    "applemail",
}

SLACK_APPS = {
    "slack",
    "discord",
    "teams",
    "mattermost",
    "zoom",
    "skype",
    "whatsapp",
}


def normalize_app_name(app_context: str | None) -> str:
    return (app_context or "").strip().lower()


def resolve_skill_id(request: AgentRequest) -> str:
    """Resolve skill id from explicit UI routing contract."""
    action = str(request.options.get("action", "")).strip().lower()
    if request.ui_tab == "Refresh" or action == "refresh_models":
        return "refresh-llms"

    if request.ui_tab == "Explain":
        return "explain"
    if request.ui_tab == "Commands":
        return "commands"
    if request.ui_tab == "Q&A":
        return "ask"

    if request.ui_tab != "Proofread":
        raise RouteError(
            code="ROUTE_UNSUPPORTED_TAB",
            message=f"Unsupported tab: {request.ui_tab}",
        )

    context = request.options.get("proofread_context")
    if context is not None:
        context = str(context).strip().lower()

    if context in {"slack", "email", "general"}:
        return f"proofread-{context}"
    if context not in {None, ""}:
        raise RouteError(
            code="ROUTE_UNMAPPED_CONTEXT",
            message=f"Unknown proofread context: {context}",
        )

    app = normalize_app_name(request.app_context)
    if app in SLACK_APPS:
        return "proofread-slack"
    if app in EMAIL_APPS:
        return "proofread-email"
    return "proofread-general"
