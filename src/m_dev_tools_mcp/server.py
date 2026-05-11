"""MCP server — the three tools that wrap the m-dev-tools org catalog.

The MCP-tool wrappers (``route_intent`` / ``describe`` / ``verify``) are
thin: each fetches its slice of the catalog (with a 60-second
in-memory cache), delegates to a pure ``*_impl`` function over the
loaded dict, and translates errors into a structured
:class:`DiscoveryError` the MCP boundary serializes for the client.

The split exists so unit tests can exercise the routing-logic in
isolation by passing in-memory fixture dicts — no network, no cache.
"""

from __future__ import annotations

import json
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from m_dev_tools_mcp._discovery import (
    fetch,
    match_intent,
    parse_typed_id,
    resolve_module_manifest_url,
)

# Raw-GitHub URLs on the org meta-repo's ``main``. The MCP server is
# always live — see AGENTS.md guardrail "No catalog state is cached on
# disk".
META_BASE = "https://raw.githubusercontent.com/m-dev-tools/.github/main"
TOOLS_URL = f"{META_BASE}/profile/tools.json"
TASK_INDEX_URL = f"{META_BASE}/profile/task_index.json"

# Cache TTL — long enough to amortize fetches across a single
# Claude-Code interaction, short enough that a freshly merged
# catalog change shows up within a minute.
CACHE_TTL_SECONDS = 60.0


class DiscoveryError(RuntimeError):
    """Raised by an MCP tool when the catalog can't be resolved.

    Carries a stable ``code`` field clients can switch on plus the
    human-readable message. The MCP framework serializes this back to
    the caller as a tool-level error.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---- in-memory catalog cache ------------------------------------------------

_CACHE: dict[str, tuple[float, Any]] = {}


def _cache_get(url: str) -> Any | None:
    cached = _CACHE.get(url)
    if cached is None:
        return None
    expiry, value = cached
    if time.monotonic() < expiry:
        return value
    _CACHE.pop(url, None)
    return None


def _cache_set(url: str, value: Any) -> None:
    _CACHE[url] = (time.monotonic() + CACHE_TTL_SECONDS, value)


def _fetch_json(url: str) -> Any:
    cached = _cache_get(url)
    if cached is not None:
        return cached
    try:
        body = fetch(url)
        data = json.loads(body)
    except (OSError, json.JSONDecodeError) as exc:
        raise DiscoveryError("catalog_fetch_failed", f"failed to fetch {url}: {exc}") from exc
    _cache_set(url, data)
    return data


def _fetch_tools() -> dict[str, Any]:
    return _fetch_json(TOOLS_URL)  # type: ignore[no-any-return]


def _fetch_task_index() -> dict[str, Any]:
    return _fetch_json(TASK_INDEX_URL)  # type: ignore[no-any-return]


# ---- route_intent ----------------------------------------------------------


def _find_intent_row(
    query: str, task_index: dict[str, Any]
) -> tuple[str, dict[str, Any]] | None:
    """Return (primary, row) for the intent ``match_intent`` picks.

    The vendored helper only returns the primary string; we need the
    full row to surface ``see_also`` after the primary. Re-walking the
    categories is cheap (one task_index has ~70 rows).
    """
    primary = match_intent(query, task_index)
    if primary is None:
        return None
    categories = task_index.get("categories", {})
    if not isinstance(categories, dict):
        return None
    for cat in categories.values():
        if not isinstance(cat, dict):
            continue
        for row in cat.values():
            if isinstance(row, dict) and row.get("primary") == primary:
                return primary, row
    return primary, {}


def route_intent_impl(query: str, task_index: dict[str, Any]) -> list[str]:
    """Pure-function routing core for ``route_intent``.

    See test_route_intent.py for the pinned contract. The pure form
    lets unit tests skip the catalog fetch.
    """
    if not query or not query.strip():
        return []
    found = _find_intent_row(query, task_index)
    if found is None:
        return []
    primary, row = found
    result = [primary]
    see_also = row.get("see_also")
    if isinstance(see_also, list):
        for item in see_also:
            if isinstance(item, str) and item not in result:
                result.append(item)
    return result


def _route_intent_through_cache(query: str) -> list[str]:
    """The cache-fetching wrapper. Separated from the MCP-tool body so
    tests can patch ``_fetch_task_index`` and assert structured
    failure handling. Any non-``DiscoveryError`` raised by the fetch
    path gets wrapped so clients always see a structured failure."""
    try:
        task_index = _fetch_task_index()
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(
            "catalog_fetch_failed",
            f"failed to fetch task_index from catalog: {exc}",
        ) from exc
    return route_intent_impl(query, task_index)


# ---- describe --------------------------------------------------------------


def describe_impl(
    typed_id: str, tools: dict[str, Any], task_index: dict[str, Any]
) -> dict[str, Any]:
    """Pure-function ``describe`` core.

    Returns a pointer-blob — URLs the caller should fetch next — for
    every supported typed-ID kind. Raises :class:`DiscoveryError` on
    grammar mismatch or unknown ID.
    """
    try:
        kind, slug, member = parse_typed_id(typed_id)
    except ValueError as exc:
        raise DiscoveryError("typed_id_malformed", str(exc)) from exc

    if kind == "recipe":
        return _describe_recipe(slug, task_index)
    if kind == "tool":
        return _describe_tool(slug, tools)
    if kind == "module":
        return _describe_module(typed_id, slug, member, tools)
    if kind == "cmd":
        return _describe_cmd(slug, member, tools)
    raise DiscoveryError("typed_id_kind_unsupported", f"unsupported typed-ID kind: {kind!r}")


def _describe_tool(slug: str, tools: dict[str, Any]) -> dict[str, Any]:
    tools_map = tools.get("tools", {})
    entry = tools_map.get(slug) if isinstance(tools_map, dict) else None
    if not isinstance(entry, dict):
        raise DiscoveryError("tool_not_found", f"tool:{slug} not in tools.json")
    blob: dict[str, Any] = {
        "typed_id": f"tool:{slug}",
        "kind": "tool",
        "repo": entry.get("repo"),
        "role": entry.get("role"),
        "license": entry.get("license"),
        "agent_instructions": entry.get("agent_instructions"),
        "verification_commands": entry.get("verification_commands"),
        "consumes": entry.get("consumes"),
    }
    for k, v in entry.items():
        if isinstance(v, str) and k.endswith("_url"):
            blob[k] = v
    return {k: v for k, v in blob.items() if v is not None}


def _describe_module(
    typed_id: str,
    slug: str,
    member: str | None,
    tools: dict[str, Any],
) -> dict[str, Any]:
    if member is None:
        raise DiscoveryError(
            "typed_id_module_missing_member",
            f"module:<repo>#<symbol> required; got {typed_id}",
        )
    manifest_url = resolve_module_manifest_url(typed_id, tools)
    if manifest_url is None:
        raise DiscoveryError(
            "module_manifest_url_unresolved",
            f"no manifest_url for {typed_id} in tools.json",
        )
    tool_blob = _describe_tool(slug, tools)
    return {
        "typed_id": typed_id,
        "kind": "module",
        "symbol": member,
        "manifest_url": manifest_url,
        "tool": tool_blob,
    }


def _describe_cmd(slug: str, member: str | None, tools: dict[str, Any]) -> dict[str, Any]:
    if member is None:
        raise DiscoveryError(
            "typed_id_cmd_missing_member",
            f"cmd:<repo>#<command> required; got cmd:{slug}",
        )
    tools_map = tools.get("tools", {})
    entry = tools_map.get(slug) if isinstance(tools_map, dict) else None
    if not isinstance(entry, dict):
        raise DiscoveryError("tool_not_found", f"tool:{slug} not in tools.json")
    commands_url = None
    for k in ("commands_url", "manifest_url"):
        v = entry.get(k)
        if isinstance(v, str):
            commands_url = v
            break
    return {
        "typed_id": f"cmd:{slug}#{member}",
        "kind": "cmd",
        "command": member,
        "commands_url": commands_url,
        "tool": _describe_tool(slug, tools),
    }


def _describe_recipe(slug: str, task_index: dict[str, Any]) -> dict[str, Any]:
    categories = task_index.get("categories", {})
    if not isinstance(categories, dict):
        raise DiscoveryError(
            "task_index_malformed", "task_index.categories is not a dict"
        )
    recipes = categories.get("recipes")
    if not isinstance(recipes, dict):
        raise DiscoveryError(
            "recipes_category_missing",
            "task_index.categories.recipes not present — "
            "this catalog predates Phase 3 Track A (PR #20)",
        )
    target = f"recipe:{slug}"
    for row_name, row in recipes.items():
        if not isinstance(row, dict):
            continue
        if row.get("primary") == target:
            html_url = (
                f"https://github.com/m-dev-tools/.github/blob/main/docs/recipes/{slug}.md"
            )
            raw_url = (
                f"https://raw.githubusercontent.com/"
                f"m-dev-tools/.github/main/docs/recipes/{slug}.md"
            )
            return {
                "typed_id": target,
                "kind": "recipe",
                "intent": row.get("intent"),
                "row_key": row_name,
                "html_url": html_url,
                "raw_url": raw_url,
                "doc": row.get("doc"),
            }
    raise DiscoveryError("recipe_not_found", f"{target} not in task_index.categories.recipes")


def _describe_through_cache(typed_id: str) -> dict[str, Any]:
    tools = _fetch_tools()
    task_index = _fetch_task_index()
    return describe_impl(typed_id, tools, task_index)


# ---- verify ----------------------------------------------------------------


def _coerce_repo_slug(repo: str) -> str:
    """Accept either ``m-cli`` (bare slug) or ``tool:m-cli`` (typed ID).

    Non-``tool:`` typed IDs are rejected with ``verify_only_accepts_tools``
    so callers don't accidentally pass a ``module:`` / ``recipe:`` /
    ``cmd:`` ID and get silently coerced to a missing-tool error.
    """
    if ":" in repo:
        try:
            kind, slug, _member = parse_typed_id(repo)
        except ValueError as exc:
            raise DiscoveryError("typed_id_malformed", str(exc)) from exc
        if kind != "tool":
            raise DiscoveryError(
                "verify_only_accepts_tools",
                f"verify expects a tool ID or bare slug; got {kind}:",
            )
        return slug
    return repo


def verify_impl(repo: str, tools: dict[str, Any]) -> list[str]:
    """Pure-function ``verify`` core. Returns the ``verification_commands``
    list a repo declared in its ``dist/repo.meta.json``.

    Does NOT execute the commands — per phase4-plan.md §3 B5, executing
    catalog-derived commands is the client's decision.
    """
    slug = _coerce_repo_slug(repo)
    tools_map = tools.get("tools", {})
    entry = tools_map.get(slug) if isinstance(tools_map, dict) else None
    if not isinstance(entry, dict):
        raise DiscoveryError("tool_not_found", f"{slug!r} not in tools.json")
    commands = entry.get("verification_commands")
    if not isinstance(commands, list):
        return []
    return [c for c in commands if isinstance(c, str)]


def _verify_through_cache(repo: str) -> list[str]:
    tools = _fetch_tools()
    return verify_impl(repo, tools)


# ---- MCP server build -------------------------------------------------------


def build_server() -> FastMCP:
    """Construct and return an MCP server with the three tools registered.

    Track A shipped this as stubs. Track B replaces each tool body with
    a call into the matching ``*_through_cache`` wrapper.
    """
    server = FastMCP("m-dev-tools-mcp")

    @server.tool()
    def route_intent(query: str) -> list[str]:
        """Return typed IDs matching the plain-English intent.

        Example: ``route_intent("parse JSON in M")`` returns
        ``["module:m-stdlib#STDJSON"]``. Results are ``[primary,
        *see_also]`` from the matched task_index row.
        """
        return _route_intent_through_cache(query)

    @server.tool()
    def describe(typed_id: str) -> dict[str, Any]:
        """Return a pointer-blob for a typed ID.

        Supported kinds: ``tool:`` / ``module:`` / ``cmd:`` / ``recipe:``.
        Does not inline payloads — returns URLs the caller should
        fetch next, keeping the catalog's "pointers, not facts"
        invariant.
        """
        return _describe_through_cache(typed_id)

    @server.tool()
    def verify(repo: str) -> list[str]:
        """List the ``verification_commands`` declared in a repo's
        ``repo.meta.json``.

        Accepts either a bare repo slug (``m-cli``) or a typed ID
        (``tool:m-cli``). Does NOT execute the commands.
        """
        return _verify_through_cache(repo)

    return server


# ---- helpers used by tests --------------------------------------------------


def _clear_cache() -> None:
    """Test helper. Drops the in-memory cache so a new fixture state is
    picked up cleanly."""
    _CACHE.clear()
