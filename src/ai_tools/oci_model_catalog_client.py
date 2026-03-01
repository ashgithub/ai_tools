"""Dedicated OCI model catalog client for list_models operations."""

from __future__ import annotations

from typing import Any

import oci


class ModelCatalogClientError(RuntimeError):
    """Raised when OCI model catalog operations fail."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _extract_error_details(exc: Exception) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if hasattr(exc, "__dict__"):
        details.update({k: v for k, v in vars(exc).items() if not k.startswith("_")})
    if not details:
        details["message"] = str(exc)
    return details


def list_active_models(settings) -> list[dict[str, str]]:
    """Fetch ACTIVE models from OCI Generative AI using dedicated catalog client."""
    profile = settings.oci.profile
    endpoint = settings.oci.service_endpoint
    compartment_id = settings.oci.compartment

    try:
        oci_config = oci.config.from_file(profile_name=profile)
    except Exception as exc:
        details = _extract_error_details(exc)
        details.update({"profile": profile})
        raise ModelCatalogClientError(
            f"OCI config bootstrap failed for profile={profile}: {exc}",
            details=details,
        ) from exc

    try:
        client = oci.generative_ai.GenerativeAiClient(
            config=oci_config,
            service_endpoint=endpoint,
            retry_strategy=oci.retry.NoneRetryStrategy(),
            timeout=(10, 240),
        )
        response = client.list_models(
            compartment_id=compartment_id,
#            lifecycle_state="ACTIVE",
            retry_strategy=oci.retry.NoneRetryStrategy(),
        )
    except Exception as exc:
        details = _extract_error_details(exc)
        details.update(
            {
                "profile": profile,
                "compartment_id": compartment_id,
                "endpoint": endpoint,
                "operation_name": details.get("operation_name", "list_models"),
            }
        )
        raise ModelCatalogClientError(
            "OCI list_models failed "
            f"(profile={profile}, compartment_id={compartment_id}, endpoint={endpoint}): {exc}",
            details=details,
        ) from exc

    normalized_models: list[dict[str, str]] = []
    for model in (getattr(response.data, "items", None) or []):
        model_id = str(getattr(model, "id", "")).strip()
        if not model_id:
            continue
        normalized_models.append(
            {
                "id": model_id,
                "display_name": str(getattr(model, "display_name", "") or model_id),
                "vendor": str(getattr(model, "vendor", "n/a")),
                "lifecycle_state": str(getattr(model, "lifecycle_state", "n/a")),
            }
        )
    return sorted(normalized_models, key=lambda item: item["id"])
