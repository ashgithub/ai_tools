#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONFIG_PATH="${AI_TOOLS_CONFIG:-${PROJECT_ROOT}/config.yaml}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Config load error: missing config file at ${CONFIG_PATH}" >&2
  exit 2
fi

if ! command -v oci >/dev/null 2>&1; then
  echo "Cache refresh failed: oci CLI not found in PATH" >&2
  exit 22
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Cache refresh failed: jq not found in PATH" >&2
  exit 22
fi

yaml_get() {
  local section="$1"
  local key="$2"
  local default_value="$3"
  local value

  value="$(awk -v section="${section}" -v key="${key}" '
    $0 ~ "^[[:space:]]*"section":[[:space:]]*$" { in_section=1; next }
    in_section && $0 ~ "^[^[:space:]]" { in_section=0 }
    in_section && $0 ~ "^[[:space:]]*"key":[[:space:]]*" {
      line=$0
      sub("^[[:space:]]*"key":[[:space:]]*", "", line)
      gsub(/^\"|\"$/, "", line)
      gsub(/^'"'"'|'"'"'$/, "", line)
      print line
      exit
    }
  ' "${CONFIG_PATH}" || true)"

  if [[ -z "${value}" ]]; then
    echo "${default_value}"
  else
    echo "${value}"
  fi
}

OCI_COMPARTMENT="$(yaml_get "oci" "compartment" "")"
OCI_PROFILE="$(yaml_get "oci" "profile" "DEFAULT")"
CACHE_DIR_RAW="$(yaml_get "model_cache" "directory" ".cache")"
CACHE_FILENAME="$(yaml_get "model_cache" "filename" "oci_models_cache.json")"
REFRESH_HOURS="$(yaml_get "model_cache" "refresh_hours" "24")"

if [[ -z "${OCI_COMPARTMENT}" ]]; then
  echo "Config load error: missing oci.compartment" >&2
  exit 2
fi

if [[ ! "${REFRESH_HOURS}" =~ ^[0-9]+$ ]]; then
  REFRESH_HOURS="24"
fi
if (( REFRESH_HOURS < 1 )); then
  REFRESH_HOURS=1
fi

if [[ "${CACHE_DIR_RAW}" = /* ]]; then
  CACHE_DIR="${CACHE_DIR_RAW}"
else
  CACHE_DIR="${PROJECT_ROOT}/${CACHE_DIR_RAW}"
fi
CACHE_PATH="${CACHE_DIR}/${CACHE_FILENAME}"

oci_output="$(oci generative-ai model-collection list-models -c "${OCI_COMPARTMENT}" --profile "${OCI_PROFILE}")" || {
  echo "Cache refresh failed: OCI CLI list-models failed for profile=${OCI_PROFILE}" >&2
  exit 22
}

models_json="$(echo "${oci_output}" | jq -c '
  [
    ((.data.items // .data // [])[]) as $item
    | ((if ($item.capabilities | type) == "string" then [$item.capabilities] else ($item.capabilities // []) end)
      | map(tostring | ascii_upcase)
      | index("CHAT")) as $has_chat
    | select($has_chat != null)
    | (($item["display-name"] // $item.displayName // $item.display_name // "") | tostring) as $name
    | select($name != "")
    | {id: $name, display_name: $name}
  ]
  | unique_by(.id)
  | sort_by(.id)
' || true)"

if [[ -z "${models_json}" ]]; then
  echo "Cache refresh failed: unable to parse OCI CLI output JSON" >&2
  exit 22
fi

models_count="$(echo "${models_json}" | jq 'length')"
if [[ "${models_count}" -eq 0 ]]; then
  echo "Cache refresh failed: OCI CLI returned no allowed CHAT models (Llama/OpenAI/Grok)" >&2
  exit 22
fi

mkdir -p "${CACHE_DIR}"
timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
tmp_file="$(mktemp "${CACHE_DIR}/.tmp_models_XXXXXX.json")"

jq -n \
  --arg ts "${timestamp}" \
  --argjson models "${models_json}" \
  '{schema_version: 1, last_refreshed_utc: $ts, source: "oci_cli.list_models", models: $models}' \
  > "${tmp_file}"

echo >> "${tmp_file}"
mv "${tmp_file}" "${CACHE_PATH}"

echo "Cache refreshed: ${CACHE_PATH} (models=${models_count})"
exit 0
