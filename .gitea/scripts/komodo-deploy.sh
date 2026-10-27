#!/bin/sh
#
# Trigger a Komodo deploy and optionally wait for it to finish.
#
# Required env:
#   KOMODO_URL           Base URL of Komodo Core, e.g. https://k.jonb.io
#   KOMODO_API_KEY       Komodo API key
#   KOMODO_API_SECRET    Komodo API secret
#   KOMODO_TARGET        Stack name/id (or Procedure name/id)
#
# Optional env:
#   KOMODO_TARGET_TYPE   "stack" (default) or "procedure"
#   KOMODO_REQUIRED      "true" to fail when KOMODO_TARGET is empty
#   KOMODO_WAIT          "true" (default) to poll until the update completes
#   KOMODO_WAIT_TIMEOUT  Seconds to wait for completion (default 600)
#   KOMODO_WAIT_INTERVAL Seconds between polls (default 10)
#
# Exits non-zero if the request is rejected or the deploy fails.

set -eu

KOMODO_TARGET_TYPE="${KOMODO_TARGET_TYPE:-stack}"
KOMODO_REQUIRED="${KOMODO_REQUIRED:-false}"
KOMODO_WAIT="${KOMODO_WAIT:-true}"
KOMODO_WAIT_TIMEOUT="${KOMODO_WAIT_TIMEOUT:-600}"
KOMODO_WAIT_INTERVAL="${KOMODO_WAIT_INTERVAL:-10}"

if [ -z "${KOMODO_TARGET:-}" ]; then
  if [ "$KOMODO_REQUIRED" = "true" ]; then
    echo "::error::KOMODO_TARGET is empty but KOMODO_REQUIRED=true" >&2
    exit 1
  fi
  echo "KOMODO_TARGET is not set - skipping Komodo deploy."
  exit 0
fi

# Explicit checks rather than ':?', whose exit status differs between
# shells (bash exits 1, dash exits 2). Keep every failure path at exit 1.
if [ -z "${KOMODO_URL:-}" ]; then
  echo "::error::KOMODO_URL is required" >&2
  exit 1
fi
if [ -z "${KOMODO_API_KEY:-}" ]; then
  echo "::error::KOMODO_API_KEY is required" >&2
  exit 1
fi
if [ -z "${KOMODO_API_SECRET:-}" ]; then
  echo "::error::KOMODO_API_SECRET is required" >&2
  exit 1
fi

# Normalise: strip any trailing slash so path joins are predictable.
KOMODO_URL="${KOMODO_URL%/}"

case "$KOMODO_TARGET_TYPE" in
  stack)
    EXECUTE="DeployStack"
    PARAMS="{\"stack\": \"${KOMODO_TARGET}\"}"
    ;;
  procedure)
    EXECUTE="RunProcedure"
    PARAMS="{\"procedure\": \"${KOMODO_TARGET}\"}"
    ;;
  *)
    echo "::error::KOMODO_TARGET_TYPE must be 'stack' or 'procedure', got '${KOMODO_TARGET_TYPE}'" >&2
    exit 1
    ;;
esac

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

# api <path> <json-body> -> writes body to $tmp, echoes HTTP status code
api() {
  curl -sS -o "$tmp" -w '%{http_code}' \
    -X POST "${KOMODO_URL}$1" \
    -H 'Content-Type: application/json' \
    -H "x-api-key: ${KOMODO_API_KEY}" \
    -H "x-api-secret: ${KOMODO_API_SECRET}" \
    -d "$2"
}

echo "Requesting ${EXECUTE} for '${KOMODO_TARGET}' on ${KOMODO_URL}"

if ! code=$(api "/execute/${EXECUTE}" "$PARAMS"); then
  echo "::error::Could not reach Komodo at ${KOMODO_URL}" >&2
  exit 1
fi

body=$(cat "$tmp")

if [ "$code" != "200" ]; then
  echo "::error::Komodo rejected ${EXECUTE} for '${KOMODO_TARGET}' (HTTP ${code})" >&2
  echo "$body" >&2
  exit 1
fi

echo "Komodo accepted the request (HTTP 200)."

# The execute endpoint returns immediately with an Update; the deploy itself
# runs asynchronously. Poll /read/GetUpdate until it reaches a terminal state.
if [ "$KOMODO_WAIT" != "true" ]; then
  echo "KOMODO_WAIT is not 'true' - not waiting for completion."
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not available - cannot poll for completion. Deploy was queued."
  exit 0
fi

update_id=$(printf '%s' "$body" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d.get("_id", {}).get("$oid", ""))
' 2>/dev/null || true)

if [ -z "$update_id" ]; then
  echo "Could not read update id from response - not polling. Deploy was queued."
  exit 0
fi

echo "Waiting for update ${update_id} (timeout ${KOMODO_WAIT_TIMEOUT}s)..."

elapsed=0
while [ "$elapsed" -lt "$KOMODO_WAIT_TIMEOUT" ]; do
  sleep "$KOMODO_WAIT_INTERVAL"
  elapsed=$((elapsed + KOMODO_WAIT_INTERVAL))

  if ! code=$(api "/read/GetUpdate" "{\"id\": \"${update_id}\"}"); then
    echo "::warning::Could not reach Komodo while polling; retrying." >&2
    continue
  fi

  if [ "$code" != "200" ]; then
    echo "::warning::GetUpdate returned HTTP ${code}; retrying." >&2
    continue
  fi

  status=$(python3 -c '
import json, sys
print(json.load(sys.stdin).get("status", ""))
' < "$tmp" 2>/dev/null || true)

  case "$status" in
    Complete)
      if python3 -c '
import json, sys
sys.exit(0 if json.load(sys.stdin).get("success") else 1)
' < "$tmp" 2>/dev/null; then
        echo "Deploy of '${KOMODO_TARGET}' completed successfully."
        exit 0
      fi
      echo "::error::Deploy of '${KOMODO_TARGET}' failed. Komodo update log:" >&2
      python3 -c '
import json, sys
d = json.load(sys.stdin)
for log in d.get("logs", []):
    print(f"  [{log.get(\"stage\", \"\")}] {log.get(\"msg\", \"\")}")
' < "$tmp" >&2 2>/dev/null || cat "$tmp" >&2
      exit 1
      ;;
    Queued|InProgress)
      echo "  ${elapsed}s: ${status}"
      ;;
    *)
      echo "  ${elapsed}s: unexpected status '${status}'"
      ;;
  esac
done

echo "::error::Timed out after ${KOMODO_WAIT_TIMEOUT}s waiting for update ${update_id}" >&2
exit 1
