"""Track A smoke tests — package imports, server scaffolds, version round-trips.

Track B's TDD suites (route_intent / describe / verify) land in their
own ``test_<tool>.py`` files; this module stays at the scaffold-only
level so the initial-commit PR can be green without yet implementing
behavior.
"""

from __future__ import annotations

import subprocess
import sys


def test_package_imports() -> None:
    import m_dev_tools_mcp

    assert m_dev_tools_mcp.__version__


def test_build_server_returns_object_with_three_tools() -> None:
    """Phase 4 contract: the MCP server exposes exactly route_intent /
    describe / verify. Manifest generator + drift gate (A5) lean on
    this — if a Track B PR adds or renames a tool, the manifest churns
    and ``make check-manifest`` flags it."""
    from m_dev_tools_mcp.server import build_server

    server = build_server()
    names = _tool_names(server)
    assert names == {"route_intent", "describe", "verify"}, names


def test_version_flag_exits_zero() -> None:
    """``python -m m_dev_tools_mcp --version`` round-trips the package version
    without booting the server. Proves the entry-point wiring landed."""
    result = subprocess.run(
        [sys.executable, "-m", "m_dev_tools_mcp", "--version"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    from m_dev_tools_mcp import __version__

    assert __version__ in result.stdout


def _tool_names(server: object) -> set[str]:
    """Pull tool names out of a FastMCP server across SDK versions.

    The MCP SDK has shifted internals across minor versions (per
    phase4-plan.md §9 risk note). This helper tolerates the two shapes
    we've seen: ``server._tools`` (older) and an async
    ``server.list_tools()`` coroutine (newer)."""
    tools = getattr(server, "_tools", None)
    if tools is not None:
        return set(tools.keys())
    list_tools = getattr(server, "list_tools", None)
    if list_tools is not None:
        import asyncio
        import inspect

        result = list_tools()
        if inspect.iscoroutine(result):
            result = asyncio.run(result)
        return {t.name for t in result}
    raise AssertionError(f"unexpected FastMCP shape: {dir(server)}")


def _resolve_tool(server: object, name: str):
    """Look up a tool's callable across SDK versions."""
    tools = getattr(server, "_tools", None)
    if tools is not None:
        entry = tools[name]
        return getattr(entry, "fn", entry)
    # Newer SDKs expose registered tools via _tool_manager / tool_manager.
    for attr in ("_tool_manager", "tool_manager"):
        mgr = getattr(server, attr, None)
        if mgr is None:
            continue
        get_tool = getattr(mgr, "get_tool", None) or getattr(mgr, "_tools", None)
        if callable(get_tool):
            entry = get_tool(name)
            return getattr(entry, "fn", entry)
        if isinstance(get_tool, dict):
            entry = get_tool[name]
            return getattr(entry, "fn", entry)
    raise AssertionError(f"cannot resolve tool {name!r} on {server!r}")
