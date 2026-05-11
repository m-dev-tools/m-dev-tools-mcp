#!/usr/bin/env python3
"""Regenerate ``dist/mcp-tools.json`` from ``server.py`` introspection.

Phase 4 §A5 drift gate. Reads each ``@server.tool()`` decorator the
``build_server()`` helper registers, extracts:

* ``name``      — the decorated callable's ``__name__``
* ``summary``   — the first non-blank line of the docstring
* ``description`` — the full docstring
* ``parameters`` — ``inspect.signature`` rendered as a JSON-Schema-shaped
  object so MCP clients (and the meta-repo catalog) can introspect
  argument names + types without importing this server

…and writes a deterministic JSON document. Running twice produces
byte-identical output (assertion-tested via ``make check-manifest``).

The MCP SDK has shifted its internals across minor versions (per
phase4-plan.md §9 risk note). The introspection path here is the same
shape used by ``tests/test_smoke.py``'s ``_tool_names`` helper —
tolerant of ``_tools`` (older), ``_tool_manager`` (mid), and
``tool_manager`` (newer) attribute layouts.

CLI::

    scripts/gen-mcp-tools-manifest.py --write dist/mcp-tools.json
    scripts/gen-mcp-tools-manifest.py --stdout
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from m_dev_tools_mcp import __version__  # noqa: E402  (sys.path patched above)
from m_dev_tools_mcp.server import build_server  # noqa: E402

# Map Python annotation names to JSON Schema primitive types. Anything
# not in this map is rendered as ``"string"`` with the original Python
# annotation kept in ``python_annotation`` so a downstream tool can
# still introspect.
PRIMITIVE_TYPES = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "list[str]": "array",
    "dict[str, Any]": "object",
}


def _resolve_tool_registry(server: object) -> dict[str, Any]:
    """Walk the FastMCP server's internals to find the {name: tool} map.

    The MCP SDK does not expose a stable public introspection API; this
    function hides the layout drift behind one place.
    """
    tools = getattr(server, "_tools", None)
    if isinstance(tools, dict):
        return tools
    for attr in ("_tool_manager", "tool_manager"):
        mgr = getattr(server, attr, None)
        if mgr is None:
            continue
        inner = getattr(mgr, "_tools", None)
        if isinstance(inner, dict):
            return inner
        list_tools = getattr(mgr, "list_tools", None)
        if callable(list_tools):
            return {t.name: t for t in list_tools()}
    raise RuntimeError(
        "cannot find a FastMCP tool registry on the server; SDK shape may have shifted"
    )


def _annotation_to_jsonschema(annotation: Any) -> dict[str, Any]:
    text = "Any" if annotation is inspect.Parameter.empty else _annotation_text(annotation)
    json_type = PRIMITIVE_TYPES.get(text, "string")
    return {"type": json_type, "python_annotation": text}


def _annotation_text(annotation: Any) -> str:
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _summary_from_doc(doc: str | None) -> str:
    if not doc:
        return ""
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _tool_entry(name: str, registered: Any) -> dict[str, Any]:
    fn = getattr(registered, "fn", registered)
    sig = inspect.signature(fn)
    params: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        params[param_name] = _annotation_to_jsonschema(param.annotation)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    return {
        "name": name,
        "summary": _summary_from_doc(fn.__doc__),
        "description": (fn.__doc__ or "").strip(),
        "parameters": {
            "type": "object",
            "properties": params,
            "required": required,
        },
        "return_annotation": _annotation_text(sig.return_annotation),
    }


def build_manifest() -> dict[str, Any]:
    server = build_server()
    registry = _resolve_tool_registry(server)
    # Sort tools by name for byte-determinism. The drift gate depends
    # on `make manifest` being idempotent.
    tools = [_tool_entry(name, registry[name]) for name in sorted(registry)]
    return {
        "$schema": "https://raw.githubusercontent.com/m-dev-tools/.github/main/profile/repo.meta.schema.json",
        "kind": "m-dev-tools-mcp.tools",
        "package": "m_dev_tools_mcp",
        "version": __version__,
        "tool_count": len(tools),
        "tools": tools,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate dist/mcp-tools.json from server.py introspection."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", type=Path, help="Write the manifest to this path.")
    group.add_argument("--stdout", action="store_true", help="Print the manifest to stdout.")
    args = parser.parse_args(argv)

    manifest = build_manifest()
    payload = json.dumps(manifest, indent=2, sort_keys=False) + "\n"

    if args.stdout:
        sys.stdout.write(payload)
        return 0

    args.write.parent.mkdir(parents=True, exist_ok=True)
    args.write.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
