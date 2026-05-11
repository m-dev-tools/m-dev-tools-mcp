"""Vendored Phase-3 discovery helpers from the org meta-repo.

Source: ``.github/profile/build/test-discovery-protocol.py`` on the
``m-dev-tools/.github`` repo. These are small pure functions over the
catalog payloads; the meta-repo is not a Python package, so the org
convention (documented in phase4-plan.md §1) is to vendor by copy.

Drift mitigation: every helper here has at least one pinned regression
test in this repo's TDD suite. If the meta-repo evolves its routing
trail and a behavior diverges, the test surfaces it as a red unit test
in this repo's CI — not as a runtime failure in a Claude Code session.

This module exposes:

* :func:`match_intent` — plain-English intent → typed-ID lookup
* :func:`parse_typed_id` — typed-ID grammar parser
* :func:`resolve_module_manifest_url` — ``module:`` ID → manifest URL
* :func:`find_module_entry` — symbol lookup in a stdlib-shaped manifest
* :func:`entry_has_signature_and_example` — completeness check
* :func:`fetch` — HTTPS / file:// resolver
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TYPED_ID_RE = re.compile(
    r"^(tool|cmd|module|rule|doc|data|workflow|task|recipe):"
    r"[a-z0-9_-]+(#[A-Za-z0-9._-]+)?$"
)


def fetch(url: str, base_dir: Path | None = None, timeout: float = 20.0) -> str:
    """Fetch a URL. Supports ``https://``, ``http://``, and ``file://``.

    ``file://./<name>`` resolves against ``base_dir``. Returns the body
    as UTF-8 text; raises on transport or decode errors so callers can
    translate into a structured MCP-tool error response.
    """
    if url.startswith("file://"):
        rel = url[len("file://") :]
        if rel.startswith("./"):
            if base_dir is None:
                raise FileNotFoundError(f"file:// URL with no base_dir: {url}")
            path = base_dir / rel[2:]
        elif rel.startswith("/"):
            path = Path(rel)
        else:
            if base_dir is None:
                raise FileNotFoundError(f"file:// URL with no base_dir: {url}")
            path = base_dir / rel
        if not path.exists():
            raise FileNotFoundError(f"fixture not found: {path}")
        return path.read_text(encoding="utf-8")
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8")  # type: ignore[no-any-return]


def match_intent(query: str, task_index: dict[str, Any]) -> str | None:
    """Match ``query`` against ``task_index.json``'s intents.

    First pass: exact case-insensitive ``intent`` string match.
    Second pass: keyword overlap (every non-stopword token in the
    query appears in the intent string), with a leading-keyword bonus
    that rewards intents starting with a query keyword.

    Returns the matched entry's ``primary`` typed-ID, or ``None`` when
    nothing matches.
    """
    if not isinstance(task_index, dict):
        return None
    categories = task_index.get("categories", {})
    if not isinstance(categories, dict):
        return None

    needle = query.lower().strip()
    keywords = [t for t in re.findall(r"[a-z0-9]+", needle) if len(t) > 2]

    for _cat_name, cat in categories.items():
        if not isinstance(cat, dict):
            continue
        for _row_name, row in cat.items():
            if not isinstance(row, dict):
                continue
            intent_str = str(row.get("intent", "")).lower()
            if intent_str == needle:
                primary = row.get("primary")
                return primary if isinstance(primary, str) else None

    best: tuple[int, int, str] | None = None
    for _cat_name, cat in categories.items():
        if not isinstance(cat, dict):
            continue
        for _row_name, row in cat.items():
            if not isinstance(row, dict):
                continue
            intent_str = str(row.get("intent", "")).lower()
            hits = sum(1 for kw in keywords if kw in intent_str)
            if hits >= max(2, len(keywords) - 1):
                first_word_match = re.findall(r"[a-z0-9]+", intent_str)
                first_word = first_word_match[0] if first_word_match else ""
                leading = 10 if first_word in keywords else 0
                primary = row.get("primary")
                if isinstance(primary, str):
                    candidate = (hits, leading, primary)
                    if best is None or (candidate[0], candidate[1]) > (best[0], best[1]):
                        best = candidate
    return best[2] if best else None


def parse_typed_id(typed_id: str) -> tuple[str, str, str | None]:
    """Return ``(kind, slug, member)`` for a typed ID.

    ``member`` is the part after ``#`` (e.g. the symbol of a stdlib
    module). Raises :class:`ValueError` on malformed input — callers
    translate into a structured MCP error.
    """
    if not TYPED_ID_RE.match(typed_id):
        raise ValueError(f"malformed typed-ID: {typed_id!r}")
    kind, rest = typed_id.split(":", 1)
    if "#" in rest:
        slug, member = rest.split("#", 1)
        return kind, slug, member
    return kind, rest, None


def resolve_module_manifest_url(typed_id: str, tools: dict[str, Any]) -> str | None:
    """Given ``module:<repo>#<symbol>``, return the manifest URL the
    catalog points at — preferring ``modules_url``, then
    ``manifest_url``, then any ``*_url`` whose value contains ``manifest``.
    """
    kind, slug, _member = parse_typed_id(typed_id)
    if kind != "module":
        return None
    tools_map = tools.get("tools", {})
    if not isinstance(tools_map, dict):
        return None
    entry = tools_map.get(slug)
    if not isinstance(entry, dict):
        return None
    for key in ("modules_url", "manifest_url", "stdlib_manifest_url"):
        v = entry.get(key)
        if isinstance(v, str):
            return v
    for k, v in entry.items():
        if isinstance(v, str) and k.endswith("_url") and "manifest" in v:
            return v
    return None


def find_module_entry(symbol: str, manifest: dict[str, Any]) -> dict[str, Any] | None:
    """Look up ``symbol`` in a stdlib-shaped manifest.

    Two supported shapes are accepted:

    * ``modules`` keyed by symbol → entry (dict-of-dicts).
    * ``modules`` as a list of entries each with a ``name`` field.
    """
    modules = manifest.get("modules")
    if isinstance(modules, dict):
        v = modules.get(symbol)
        return v if isinstance(v, dict) else None
    if isinstance(modules, list):
        for m in modules:
            if isinstance(m, dict) and m.get("name") == symbol:
                return m
    return None


def entry_has_signature_and_example(entry: dict[str, Any]) -> tuple[bool, bool]:
    """Return ``(has_signature, has_example)``.

    The stdlib-manifest shape nests per-label data under ``labels``: an
    entry counts as having a signature / example if at least one label
    exposes one. Falls back to top-level fields for non-stdlib manifests.
    """
    has_sig = False
    has_ex = False

    def _check_dict(d: dict[str, Any]) -> None:
        nonlocal has_sig, has_ex
        if "signature" in d and d["signature"]:
            has_sig = True
        if d.get("example") or d.get("examples"):
            has_ex = True

    _check_dict(entry)

    labels = entry.get("labels")
    if isinstance(labels, dict):
        for v in labels.values():
            if isinstance(v, dict):
                _check_dict(v)
    elif isinstance(labels, list):
        for v in labels:
            if isinstance(v, dict):
                _check_dict(v)

    return has_sig, has_ex
