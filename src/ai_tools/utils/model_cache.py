"""Model catalog loader for on-disk cache consumed by the GUI."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class ModelCatalogBootstrapError(RuntimeError):
    """Raised when the model catalog cannot be initialized without cache."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _project_root() -> Path:
    # .../src/ai_tools/utils/model_cache.py -> project root is parents[3]
    return Path(__file__).resolve().parents[3]


def _cache_path(settings) -> Path:
    cache_dir = Path(settings.model_cache.directory)
    if not cache_dir.is_absolute():
        cache_dir = _project_root() / cache_dir
    return cache_dir / settings.model_cache.filename


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _age_hours(last_refreshed: datetime | None) -> float | None:
    if not last_refreshed:
        return None
    delta = _utc_now() - last_refreshed
    return max(0.0, delta.total_seconds() / 3600.0)


def _normalize_model_entries(raw_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in raw_entries:
        model_id = str(item.get("id", "")).strip()
        if not model_id:
            continue
        display_name = str(item.get("display_name") or model_id).strip()
        deduped[model_id] = {"id": model_id, "display_name": display_name}
    return [deduped[k] for k in sorted(deduped.keys())]


def _resolve_default_model(settings, models: list[dict[str, Any]], cached_default: str | None = None) -> str | None:
    if not models:
        return None
    ids = {m["id"] for m in models}
    if cached_default and cached_default in ids:
        return cached_default
    preferred = settings.model_cache.preferred_default
    if preferred and preferred in ids:
        return preferred
    configured = settings.oci.default_model
    if configured and configured in ids:
        return configured
    return models[0]["id"]


def _mark_default(models: list[dict[str, Any]], default_model: str | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for model in models:
        result.append(
            {
                "id": model["id"],
                "display_name": model.get("display_name", model["id"]),
                "is_default": model["id"] == default_model,
            }
        )
    return result


def _read_cache(path: Path, settings) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Model cache is unreadable at %s; treating as cache miss.", path)
        return None

    models = payload.get("models")
    if not isinstance(models, list):
        return None

    normalized = _normalize_model_entries(models)
    if not normalized:
        return None

    default_model = _resolve_default_model(
        settings=settings,
        models=normalized,
        cached_default=payload.get("default_model"),
    )
    if not default_model:
        return None

    schema_version = payload.get("schema_version", SCHEMA_VERSION)
    if not isinstance(schema_version, int):
        schema_version = SCHEMA_VERSION

    return {
        "schema_version": schema_version,
        "last_refreshed_utc": payload.get("last_refreshed_utc"),
        "source": payload.get("source", "oci.list_models"),
        "default_model": default_model,
        "models": _mark_default(normalized, default_model),
    }

def get_cached_or_refreshed_models(settings) -> dict[str, Any]:
    """Load model catalog strictly from local cache file."""

    cache_file = _cache_path(settings)
    cached = _read_cache(cache_file, settings=settings)

    if not cached:
        raise ModelCatalogBootstrapError(
            "Model cache not found or invalid. "
            f"Expected cache file: {cache_file}. "
            "Run clients/refresh_model_cache_via_oci_cli.py first."
        )

    last_refreshed = _parse_utc(cached.get("last_refreshed_utc"))
    cached["source"] = "cache_hit"
    cached["cache_age_hours"] = _age_hours(last_refreshed)
    return cached
