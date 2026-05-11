"""Console entry point — boots the MCP server's stdio transport.

Track B implements the three tool callbacks. Track A ships the entry
plumbing only: ``python -m m_dev_tools_mcp`` and the
``m-dev-tools-mcp`` console-script both land here.
"""

from __future__ import annotations

import sys

from m_dev_tools_mcp.server import build_server


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in {"--version", "-V"}:
        from m_dev_tools_mcp import __version__

        print(__version__)
        return 0
    server = build_server()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
