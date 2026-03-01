#!/usr/bin/env python3
"""Refresh model cache using OCI CLI list-models output."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from ai_tools.utils.config import get_settings

SCHEMA_VERSION = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def _is_stale(last_refreshed: datetime | None, refresh_hours: int) -> bool:
    if not last_refreshed:
        return True
    max_age = max(1, refresh_hours)
    hours = (_utc_now() - last_refreshed).total_seconds() / 3600.0
    return hours >= max_age


def _read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _normalize_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    deduped: dict[str, dict[str, str]] = {}
    for item in items:
        capabilities_raw = item.get("capabilities", [])
        if isinstance(capabilities_raw, str):
            capabilities = [capabilities_raw]
        elif isinstance(capabilities_raw, list):
            capabilities = [str(cap).strip().upper() for cap in capabilities_raw]
        else:
            capabilities = []
        if "CHAT" not in capabilities:
            continue

        model_id = str(item.get("id", "")).strip()
        if not model_id:
            continue
        display_name = (
            item.get("display-name")
            or item.get("displayName")
            or item.get("display_name")
            or ""
        )
        model_name = str(display_name).strip()
        # Keep UI/cache values human-friendly; skip entries without a display name.
        if not model_name:
            continue
        model_id_lower = model_id.lower()
        model_name_lower = model_name.lower()
        vendor_lower = str(item.get("vendor", "")).strip().lower()
        allowed_family = (
            model_name_lower.startswith("meta.llama")
            or model_name_lower.startswith("openai.")
            or model_name_lower.startswith("xai.grok")
            or model_id_lower.startswith("meta.llama")
            or model_id_lower.startswith("openai.")
            or model_id_lower.startswith("xai.grok")
            or "llama" in vendor_lower
            or "openai" in vendor_lower
            or "grok" in vendor_lower
            or "xai" in vendor_lower
        )
        if not allowed_family:
            continue

        deduped[model_name] = {
            "id": model_name,
            "display_name": model_name,
            "source_id": model_id,
            "vendor": str(item.get("vendor", "n/a")),
            "lifecycle_state": str(item.get("lifecycle-state") or item.get("lifecycleState") or "n/a"),
        }
    return [deduped[k] for k in sorted(deduped.keys())]


def _resolve_default(settings, models: list[dict[str, str]]) -> str:
    ids = {m["id"] for m in models}
    preferred = settings.model_cache.preferred_default
    if preferred and preferred in ids:
        return preferred
    configured = settings.oci.default_model
    if configured and configured in ids:
        return configured
    return models[0]["id"]


def _write_cache_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(path.parent), prefix=".tmp_models_", suffix=".json", delete=False
    ) as tmp:
        json.dump(payload, tmp, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _run_oci_cli(settings) -> list[dict[str, Any]]:
    command = [
        "oci",
        "generative-ai",
        "model-collection",
        "list-models",
        "-c",
        settings.oci.compartment,
        "--profile",
        settings.oci.profile,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "OCI CLI list-models failed "
            f"(exit={result.returncode}). stderr: {result.stderr.strip() or '[empty]'}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse OCI CLI JSON output: {exc}") from exc

    data = payload.get("data")
    items: Any = None
    if isinstance(data, dict):
        items = data.get("items")
    elif isinstance(data, list):
        # Some OCI CLI commands return a direct list in `data`.
        items = data
    if not isinstance(items, list):
        raise RuntimeError("Unexpected OCI CLI output: expected `data.items` or `data` list")
    return items


def main() -> int:
    try:
        settings = get_settings()
    except Exception as exc:
        print(f"Config load error: {exc}", file=sys.stderr)
        return 2

    cache_file = _cache_path(settings)
    existing = _read_cache(cache_file)
    last_refreshed = _parse_utc(existing.get("last_refreshed_utc")) if isinstance(existing, dict) else None

    if existing and not _is_stale(last_refreshed, settings.model_cache.refresh_hours):
        print(f"Cache is fresh; no refresh needed: {cache_file}")
        return 0

    try:
        raw_items = _run_oci_cli(settings)
        models = _normalize_items(raw_items)
        if not models:
            raise RuntimeError("OCI CLI returned no allowed CHAT models (Llama/OpenAI/Grok)")
        default_model = _resolve_default(settings, models)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "last_refreshed_utc": _utc_now().isoformat().replace("+00:00", "Z"),
            "source": "oci_cli.list_models",
            "default_model": default_model,
            "models": [
                {
                    "id": m["id"],
                    "display_name": m["display_name"],
                    "is_default": m["id"] == default_model,
                }
                for m in models
            ],
        }
        _write_cache_atomic(cache_file, payload)
        print(f"Cache refreshed: {cache_file} (models={len(models)})")
        return 0
    except Exception as exc:
        print(f"Cache refresh failed: {exc}", file=sys.stderr)
        return 22


if __name__ == "__main__":
    raise SystemExit(main())
