"""TDD coverage for ``route_intent`` (Phase 4 Track B §3 B1 / B2).

Pins:

* Exact intent match — case-insensitive, returns ``[primary]``.
* Fuzzy match (keyword overlap) — same return shape, ranks the row
  whose ``primary`` wins the vendored ``match_intent`` helper.
* Empty query → ``[]`` (no catalog round-trip).
* No match → ``[]`` (calibrate-the-rocket-booster baseline).
* ``see_also`` entries surface after ``primary`` in the result list.
* Catalog fetch failure → raises a structured ``DiscoveryError`` so
  the MCP boundary serializes it back to the client cleanly; the
  server does NOT silently fall back to an empty list.

The route_intent impl in ``server.py`` is split into two pieces:

* ``route_intent_impl(query, task_index)`` — pure function over a
  loaded task_index dict. Easy to test with in-memory fixtures.
* ``route_intent(query)`` — the MCP-tool wrapper that fetches the
  catalog and delegates.

Tests target the pure function for the routing-logic cases and the
wrapper for the network-failure case.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from m_dev_tools_mcp.server import DiscoveryError, route_intent_impl

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def task_index() -> dict:
    return json.loads((FIXTURES / "task_index.json").read_text(encoding="utf-8"))


@pytest.fixture
def task_index_with_see_also() -> dict:
    """task_index variant exercising see_also surfacing — fixture-faithful
    plus one row that adds the see_also field. Keeping this inline
    instead of editing the on-disk fixture lets the upstream Phase 3
    fixture stay byte-identical to the meta-repo's copy."""
    return {
        "kind": "m-dev-tools.task-index",
        "categories": {
            "lib": {
                "json_parse_with_alts": {
                    "intent": "Parse JSON text into an M tree",
                    "primary": "module:m-stdlib#STDJSON",
                    "see_also": [
                        "cmd:m-cli#examples",
                        "recipe:use-stdlib-module",
                    ],
                }
            }
        },
    }


def test_route_intent_exact_match(task_index: dict) -> None:
    """Exact case-insensitive intent string match."""
    assert route_intent_impl("Parse JSON text into an M tree", task_index) == [
        "module:m-stdlib#STDJSON"
    ]


def test_route_intent_exact_match_case_insensitive(task_index: dict) -> None:
    assert route_intent_impl("parse json text into an m tree", task_index) == [
        "module:m-stdlib#STDJSON"
    ]


def test_route_intent_fuzzy_keyword_overlap(task_index: dict) -> None:
    """Token overlap fallback. ``parse JSON in M`` shares ≥ 2 keywords
    with ``Parse JSON text into an M tree`` and so resolves."""
    assert route_intent_impl("parse JSON in M", task_index) == ["module:m-stdlib#STDJSON"]


def test_route_intent_empty_query_returns_empty(task_index: dict) -> None:
    """Empty queries must short-circuit — no fuzzy-matching surface."""
    assert route_intent_impl("", task_index) == []
    assert route_intent_impl("   ", task_index) == []


def test_route_intent_no_match_returns_empty(task_index: dict) -> None:
    """Off-topic queries return ``[]``. No silent fallback to the first
    intent in the catalog."""
    assert route_intent_impl("calibrate the rocket booster", task_index) == []


def test_route_intent_see_also_surfaces_after_primary(task_index_with_see_also: dict) -> None:
    """see_also entries follow primary in the result list, in
    catalog-declared order."""
    result = route_intent_impl(
        "Parse JSON text into an M tree", task_index_with_see_also
    )
    assert result == [
        "module:m-stdlib#STDJSON",
        "cmd:m-cli#examples",
        "recipe:use-stdlib-module",
    ]


def test_route_intent_see_also_dedupes_primary(task_index_with_see_also: dict) -> None:
    """If a misconfigured row repeats ``primary`` inside ``see_also``,
    the wrapper dedupes — clients shouldn't see noise from upstream
    catalog quirks."""
    ti = task_index_with_see_also
    row = ti["categories"]["lib"]["json_parse_with_alts"]
    row["see_also"] = [row["primary"], "cmd:m-cli#examples"]
    result = route_intent_impl("Parse JSON text into an M tree", ti)
    assert result == ["module:m-stdlib#STDJSON", "cmd:m-cli#examples"]


def test_route_intent_malformed_task_index_returns_empty() -> None:
    """A task_index whose ``categories`` field is the wrong shape must
    not crash route_intent — return ``[]`` and let the catalog drift
    gate surface the schema violation upstream."""
    assert route_intent_impl("anything", {"categories": "not-a-dict"}) == []
    assert route_intent_impl("anything", {}) == []


def test_route_intent_wrapper_raises_on_fetch_failure() -> None:
    """The MCP-tool wrapper raises ``DiscoveryError`` (a structured
    failure) when the catalog can't be fetched. No silent fallback."""
    from m_dev_tools_mcp import server as server_mod

    def boom(*_args: object, **_kwargs: object) -> dict:
        raise ConnectionError("upstream catalog unreachable")

    with patch.object(server_mod, "_fetch_task_index", side_effect=boom):
        with pytest.raises(DiscoveryError) as exc_info:
            server_mod._route_intent_through_cache("Parse JSON text into an M tree")
        assert "catalog" in str(exc_info.value).lower()
