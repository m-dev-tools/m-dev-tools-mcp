"""TDD coverage for ``verify`` (Phase 4 Track B §3 B5).

``verify`` reads the ``verification_commands`` field a repo declared
in its ``dist/repo.meta.json`` (surfaced into ``tools.json`` as a
top-level field on each tool entry) and returns it. **It does NOT
execute the commands** — see phase4-plan.md §3 B5 rationale.

Accepts either a bare slug (``m-cli``) or a typed ID (``tool:m-cli``).
"""

from __future__ import annotations

import pytest

from m_dev_tools_mcp.server import DiscoveryError, verify_impl


@pytest.fixture
def tools() -> dict:
    return {
        "tools": {
            "m-cli": {
                "id": "tool:m-cli",
                "verification_commands": ["make check", "m doctor"],
            },
            "m-stdlib": {
                "id": "tool:m-stdlib",
                "verification_commands": ["make check"],
            },
            "no-commands": {
                "id": "tool:no-commands",
            },
        }
    }


def test_verify_bare_slug_returns_command_list(tools: dict) -> None:
    assert verify_impl("m-cli", tools) == ["make check", "m doctor"]


def test_verify_typed_id_sugar(tools: dict) -> None:
    """``tool:m-cli`` is the documented form; the bare slug is sugar
    for it. Both must return the same list."""
    assert verify_impl("tool:m-cli", tools) == ["make check", "m doctor"]


def test_verify_unknown_repo_raises(tools: dict) -> None:
    with pytest.raises(DiscoveryError) as exc_info:
        verify_impl("nonexistent-repo", tools)
    assert exc_info.value.code == "tool_not_found"


def test_verify_typed_id_non_tool_kind_raises(tools: dict) -> None:
    """A non-``tool:`` typed ID (``module:`` / ``recipe:`` / …) is
    nonsensical for verify — repos are the unit, not symbols. Surface
    a clear error rather than silently looking up the slug."""
    with pytest.raises(DiscoveryError) as exc_info:
        verify_impl("module:m-stdlib#STDJSON", tools)
    assert exc_info.value.code == "verify_only_accepts_tools"


def test_verify_repo_without_verification_commands_returns_empty(tools: dict) -> None:
    """A repo that didn't declare ``verification_commands`` in its
    repo.meta.json returns ``[]`` — not an error. Cleanly distinguishes
    "no commands declared" from "repo doesn't exist"."""
    assert verify_impl("no-commands", tools) == []


def test_verify_malformed_typed_id_raises(tools: dict) -> None:
    with pytest.raises(DiscoveryError) as exc_info:
        verify_impl("tool:M-CLI", tools)  # uppercase slug fails grammar
    assert exc_info.value.code == "typed_id_malformed"


def test_verify_does_not_execute_commands(tools: dict) -> None:
    """Defensive: the return value is the literal list. If a future
    refactor ever shells out, this assertion still holds since
    ``verify_impl`` is a pure function over the loaded catalog."""
    out = verify_impl("m-cli", tools)
    assert all(isinstance(c, str) for c in out)
    assert out == tools["tools"]["m-cli"]["verification_commands"]
