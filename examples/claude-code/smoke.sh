#!/usr/bin/env bash
# Agent-free MCP-server smoke check. Per phase4-plan.md §4 C2:
# resolve the canonical "parse JSON in M" intent through the
# `route_intent` tool and confirm the typed ID lands in stdout.
#
# Default mode: pin to git main, install on demand via uvx. CI and
# local-dev users with the package already installed in a venv can
# point M_DEV_TOOLS_MCP_BIN at it to skip the uvx round-trip:
#
#   M_DEV_TOOLS_MCP_BIN=$(pwd)/.venv/bin/m-dev-tools-mcp ./smoke.sh
#
# Exit codes:
#   0 — canonical query resolved (the typed ID was in the response)
#   1 — server emitted a response that did NOT include the typed ID
#   2 — the underlying CLI exited non-zero (network, install,
#       structured DiscoveryError)

set -euo pipefail

QUERY="parse JSON in M"
EXPECTED='"module:m-stdlib#STDJSON"'

if [[ -n "${M_DEV_TOOLS_MCP_BIN:-}" ]]; then
    CMD=("$M_DEV_TOOLS_MCP_BIN")
else
    CMD=(uvx --from "git+https://github.com/m-dev-tools/m-dev-tools-mcp@main" m-dev-tools-mcp)
fi

echo "→ ${CMD[*]} --tool route_intent --query \"$QUERY\""

set +e
RESULT="$("${CMD[@]}" --tool route_intent --query "$QUERY")"
RC=$?
set -e

if [[ $RC -ne 0 ]]; then
    echo "ERROR: CLI exited rc=$RC; response was:" >&2
    echo "$RESULT" >&2
    exit 2
fi

echo "$RESULT"

if grep -qF "$EXPECTED" <<<"$RESULT"; then
    echo "✓ canonical query resolved to $EXPECTED"
    exit 0
fi

echo "ERROR: response did not contain $EXPECTED" >&2
exit 1
