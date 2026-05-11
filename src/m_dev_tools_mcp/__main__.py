"""Console entry point.

Two modes:

* **MCP server mode (default)** — ``m-dev-tools-mcp`` with no args
  boots the stdio MCP server. Each ``@server.tool()`` is exposed to
  the connected MCP client. This is the path Claude Code / Codex /
  Continue use.

* **CLI smoke mode** — ``m-dev-tools-mcp --tool route_intent --query
  "…"`` runs one tool call out of process and prints the JSON
  response on stdout. The smoke.sh under
  ``examples/claude-code/smoke.sh`` shells this surface so an
  agent-free environment can verify the MCP server resolves the
  canonical query.

Exit codes (CLI smoke mode):

* ``0`` — success
* ``2`` — usage error (unknown tool, missing required flag, etc.)
* ``3`` — :class:`DiscoveryError` from the tool itself; stdout
  carries a JSON error blob ``{"error": true, "code": "...",
  "message": "..."}`` so a shell script can switch on the code.

A missing ``--query`` / ``--typed-id`` / ``--repo`` is enforced
manually (argparse can't model "this flag is required only when
--tool=X" natively). The check happens after parsing so the error
message can name the missing flag directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from m_dev_tools_mcp import __version__
from m_dev_tools_mcp.server import (
    DiscoveryError,
    _describe_through_cache,
    _route_intent_through_cache,
    _verify_through_cache,
    build_server,
)

_TOOL_CHOICES = ("route_intent", "describe", "verify")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m-dev-tools-mcp",
        description=__doc__.splitlines()[0] if __doc__ else "",
        exit_on_error=False,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Print the package version and exit.",
    )
    parser.add_argument(
        "--tool",
        choices=_TOOL_CHOICES,
        help="Run a single tool call out of process and print its JSON response.",
    )
    parser.add_argument("--query", help="Query string for --tool route_intent.")
    parser.add_argument("--typed-id", dest="typed_id", help="Typed ID for --tool describe.")
    parser.add_argument("--repo", help="Repo slug or typed ID for --tool verify.")
    return parser


def _run_tool(args: argparse.Namespace) -> int:
    tool = args.tool
    if tool == "route_intent":
        if args.query is None:
            print("error: --tool route_intent requires --query", file=sys.stderr)
            return 2
        result: Any = _route_intent_through_cache(args.query)
    elif tool == "describe":
        if args.typed_id is None:
            print("error: --tool describe requires --typed-id", file=sys.stderr)
            return 2
        result = _describe_through_cache(args.typed_id)
    elif tool == "verify":
        if args.repo is None:
            print("error: --tool verify requires --repo", file=sys.stderr)
            return 2
        result = _verify_through_cache(args.repo)
    else:  # pragma: no cover — argparse choices guard
        print(f"error: unknown --tool {tool!r}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except (argparse.ArgumentError, argparse.ArgumentTypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except SystemExit as exc:
        # exit_on_error=False covers most paths, but unknown --tool
        # choices still trigger SystemExit. Translate into rc=2.
        return int(exc.code) if isinstance(exc.code, int) else 2

    if args.version:
        print(__version__)
        return 0

    if args.tool is not None:
        try:
            return _run_tool(args)
        except DiscoveryError as exc:
            blob = {"error": True, "code": exc.code, "message": str(exc)}
            print(json.dumps(blob, indent=2))
            return 3

    # Default: boot the MCP server's stdio transport.
    server = build_server()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
