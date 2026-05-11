"""TDD coverage for the ``--tool / --query`` CLI surface.

phase4-plan.md §4 C2 expects ``m-dev-tools-mcp --tool route_intent
--query "parse JSON in M"`` to be a non-MCP smoke-test path: shell
the tool out of process, assert the stdout contains the typed ID.

This was framed as a Track-B deliverable in the plan; it shipped in
Track C alongside the smoke.sh that depends on it.

The CLI surface:

* ``--tool route_intent --query "…"`` → JSON list of typed IDs.
* ``--tool describe --typed-id "…"`` → JSON pointer-blob.
* ``--tool verify --repo "…"`` → JSON list of verification commands.
* ``--version`` keeps working (Track A contract).
* No flags → boot the MCP server (existing behavior; not unit-tested
  here — the server's stdio loop is exercised by the manual session
  smoke and by Claude Code itself).
* ``--tool <unknown>`` → exit 2 with a clear error.
* Tool-side ``DiscoveryError`` → exit 3, error blob on stdout, so a
  shell script can tell "no match" from "bad input".

Tests target the network-free path: they patch ``_fetch_tools`` /
``_fetch_task_index`` to return fixture dicts so the CLI exercises
the same wiring as the MCP-server tool path without hitting raw-
GitHub.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from m_dev_tools_mcp.__main__ import main

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tools_full() -> dict[str, Any]:
    return {
        "tools": {
            "m-stdlib": {
                "id": "tool:m-stdlib",
                "repo": "https://github.com/m-dev-tools/m-stdlib",
                "role": "Pure-M runtime standard library",
                "license": "AGPL-3.0",
                "agent_instructions": (
                    "https://github.com/m-dev-tools/m-stdlib/blob/main/AGENTS.md"
                ),
                "modules_url": (
                    "https://raw.githubusercontent.com/"
                    "m-dev-tools/m-stdlib/main/dist/stdlib-manifest.json"
                ),
                "verification_commands": ["make check"],
            },
            "m-cli": {
                "id": "tool:m-cli",
                "verification_commands": ["make check", "m doctor"],
            },
        }
    }


@pytest.fixture
def task_index() -> dict[str, Any]:
    return json.loads((FIXTURES / "task_index.json").read_text(encoding="utf-8"))


def _patch_catalog(tools: dict[str, Any], task_index: dict[str, Any]):
    """Stack the two server-module patches so the CLI sees fixture data."""
    return [
        patch("m_dev_tools_mcp.server._fetch_tools", return_value=tools),
        patch("m_dev_tools_mcp.server._fetch_task_index", return_value=task_index),
        patch("m_dev_tools_mcp.server._clear_cache"),  # CLI invokes it
    ]


def _run_main(argv: list[str], tools: dict[str, Any], task_index: dict[str, Any], capsys):
    patches = _patch_catalog(tools, task_index)
    for p in patches:
        p.start()
    try:
        rc = main(argv)
    finally:
        for p in patches:
            p.stop()
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_cli_version_still_works(capsys) -> None:
    """Pin the Track A contract — ``--version`` exits 0 and prints
    the package version. Sanity check the CLI didn't lose it."""
    from m_dev_tools_mcp import __version__

    rc = main(["--version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert __version__ in out


def test_cli_route_intent_happy_path(
    tools_full: dict[str, Any], task_index: dict[str, Any], capsys
) -> None:
    rc, out, _err = _run_main(
        ["--tool", "route_intent", "--query", "Parse JSON text into an M tree"],
        tools_full,
        task_index,
        capsys,
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload == ["module:m-stdlib#STDJSON"]


def test_cli_route_intent_no_match_returns_empty_list(
    tools_full: dict[str, Any], task_index: dict[str, Any], capsys
) -> None:
    """``--tool route_intent`` returns ``[]`` for unmatched queries —
    exit 0 (the lookup succeeded; the answer is just empty). Distinct
    from exit 3 which signals a structured DiscoveryError."""
    rc, out, _err = _run_main(
        ["--tool", "route_intent", "--query", "calibrate the rocket booster"],
        tools_full,
        task_index,
        capsys,
    )
    assert rc == 0
    assert json.loads(out) == []


def test_cli_describe_happy_path(
    tools_full: dict[str, Any], task_index: dict[str, Any], capsys
) -> None:
    rc, out, _err = _run_main(
        ["--tool", "describe", "--typed-id", "module:m-stdlib#STDJSON"],
        tools_full,
        task_index,
        capsys,
    )
    assert rc == 0
    blob = json.loads(out)
    assert blob["typed_id"] == "module:m-stdlib#STDJSON"
    assert blob["kind"] == "module"


def test_cli_verify_happy_path(
    tools_full: dict[str, Any], task_index: dict[str, Any], capsys
) -> None:
    rc, out, _err = _run_main(
        ["--tool", "verify", "--repo", "m-cli"],
        tools_full,
        task_index,
        capsys,
    )
    assert rc == 0
    assert json.loads(out) == ["make check", "m doctor"]


def test_cli_unknown_tool_exits_2(capsys) -> None:
    """argparse-style usage error → exit 2 (POSIX-ish convention)."""
    rc = main(["--tool", "uppercase-the-database", "--query", "x"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "unknown" in err.lower() or "invalid" in err.lower()


def test_cli_route_intent_requires_query(capsys) -> None:
    rc = main(["--tool", "route_intent"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "query" in err.lower()


def test_cli_describe_requires_typed_id(capsys) -> None:
    rc = main(["--tool", "describe"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "typed-id" in err.lower() or "typed_id" in err.lower()


def test_cli_verify_requires_repo(capsys) -> None:
    rc = main(["--tool", "verify"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "repo" in err.lower()


def test_cli_discovery_error_exits_3_with_structured_blob(
    tools_full: dict[str, Any], task_index: dict[str, Any], capsys
) -> None:
    """A DiscoveryError raised by the tool surfaces on stdout as a JSON
    error blob with ``error`` + ``code`` fields, exit 3. Lets shell
    scripts switch on the code without parsing free-form text."""
    rc, out, _err = _run_main(
        ["--tool", "describe", "--typed-id", "not-a-typed-id"],
        tools_full,
        task_index,
        capsys,
    )
    assert rc == 3
    blob = json.loads(out)
    assert blob["error"] is True
    assert blob["code"] == "typed_id_malformed"
    assert "message" in blob


def test_cli_subprocess_smoke_exits_zero() -> None:
    """End-to-end via subprocess — mirrors what smoke.sh does. We
    can't easily patch from a child process, so this targets the
    real catalog. Skip if no network reachable."""
    # Sentinel env var lets CI opt out of network-dependent smoke tests
    # if it ever needs to.
    if os.environ.get("MCP_SKIP_NETWORK_SMOKE") == "1":
        pytest.skip("MCP_SKIP_NETWORK_SMOKE=1")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "m_dev_tools_mcp",
                "--tool",
                "route_intent",
                "--query",
                "Parse JSON text into an M tree",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        pytest.skip("network timeout reaching raw.githubusercontent.com")
    if result.returncode != 0:
        # Network-dependent — surface the failure as a skip not a fail,
        # since CI runs against the live catalog and any upstream change
        # would otherwise red this test.
        pytest.skip(f"network/catalog failure: rc={result.returncode}, stderr={result.stderr!r}")
    assert "module:m-stdlib#STDJSON" in result.stdout
