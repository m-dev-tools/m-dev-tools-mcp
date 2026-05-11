"""MCP server scaffold — Track A ships tool stubs only.

The three tools (``route_intent``, ``describe``, ``verify``) are wired
through the MCP framework so the manifest-introspection script can
discover them, but their bodies raise ``NotImplementedError``. Track B
fills in real behavior (see phase4-plan.md §3 B1–B6).

The scaffold is structured so that:

* ``build_server()`` returns an MCP ``Server`` instance with the three
  tools registered. Importable; used by the manifest generator without
  starting an event loop.
* ``__main__.main()`` calls ``build_server().run()`` to start stdio
  transport.
* Each tool's docstring is the user-visible description in the MCP
  manifest; keep it terse and accurate.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


def build_server() -> FastMCP:
    """Construct and return an MCP server with the three tools registered.

    Returns a ``FastMCP`` instance from the MCP Python SDK. Track A's
    smoke test only asserts the function is callable and the registered
    tool count matches; running the server is a Track C concern.
    """
    server = FastMCP("m-dev-tools-mcp")

    @server.tool()
    def route_intent(query: str) -> list[str]:
        """Return typed IDs matching the plain-English intent.

        Example: ``route_intent("parse JSON in M")`` returns
        ``["module:m-stdlib#STDJSON"]`` once Track B lands. Track A
        leaves the body as a placeholder.
        """
        raise NotImplementedError("Track B (phase4-plan.md §3 B2) implements this.")

    @server.tool()
    def describe(typed_id: str) -> dict[str, Any]:
        """Return a pointer-blob for a typed ID (``tool:`` / ``module:`` / ``cmd:`` / ``recipe:``).

        Does not inline the underlying payloads — returns URLs the caller
        should fetch next. Implemented in Track B (§3 B4).
        """
        raise NotImplementedError("Track B (phase4-plan.md §3 B4) implements this.")

    @server.tool()
    def verify(repo: str) -> list[str]:
        """List the ``verification_commands`` declared in a repo's ``repo.meta.json``.

        Returns the command strings — does NOT execute them (executing
        catalog-derived commands is a client/agent decision; see Track B
        §3 B5 rationale).
        """
        raise NotImplementedError("Track B (phase4-plan.md §3 B5) implements this.")

    return server
