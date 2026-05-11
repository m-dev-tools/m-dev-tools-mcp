"""TDD coverage for ``describe`` (Phase 4 Track B §3 B3 / B4).

Pins the pointer-blob shape per typed-ID kind:

* ``tool:<slug>`` — top-level tool entry with all ``*_url`` pointers.
* ``module:<slug>#<symbol>`` — manifest_url drill-in.
* ``cmd:<slug>#<command>`` — commands_url + parent tool.
* ``recipe:<slug>`` — resolved through ``task_index.categories.recipes``.

And the error contract:

* malformed typed-ID → ``DiscoveryError(typed_id_malformed)``.
* unknown tool / recipe / kind → structured DiscoveryError.
* module without ``#`` member → ``typed_id_module_missing_member``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m_dev_tools_mcp.server import DiscoveryError, describe_impl

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tools() -> dict:
    return json.loads((FIXTURES / "tools.json").read_text(encoding="utf-8"))


@pytest.fixture
def task_index() -> dict:
    return json.loads((FIXTURES / "task_index.json").read_text(encoding="utf-8"))


@pytest.fixture
def tools_full() -> dict:
    """In-memory tools.json that has m-cli too — the on-disk fixture
    only carries m-stdlib, but cmd: / tool: tests need a second
    repo's shape."""
    return {
        "tools": {
            "m-stdlib": {
                "id": "tool:m-stdlib",
                "repo": "https://github.com/m-dev-tools/m-stdlib",
                "role": "Pure-M runtime standard library",
                "license": "AGPL-3.0",
                "agent_instructions": "https://github.com/m-dev-tools/m-stdlib/blob/main/AGENTS.md",
                "modules_url": "https://raw.githubusercontent.com/m-dev-tools/m-stdlib/main/dist/stdlib-manifest.json",
                "repo_meta_url": "https://raw.githubusercontent.com/m-dev-tools/m-stdlib/main/dist/repo.meta.json",
                "consumes": [],
                "verification_commands": ["make check"],
            },
            "m-cli": {
                "id": "tool:m-cli",
                "repo": "https://github.com/m-dev-tools/m-cli",
                "role": "Canonical M CLI — fmt / lint / test / coverage / watch / lsp",
                "license": "AGPL-3.0",
                "agent_instructions": "https://github.com/m-dev-tools/m-cli/blob/main/AGENTS.md",
                "commands_url": "https://raw.githubusercontent.com/m-dev-tools/m-cli/main/dist/commands.json",
                "repo_meta_url": "https://raw.githubusercontent.com/m-dev-tools/m-cli/main/dist/repo.meta.json",
                "consumes": ["tool:tree-sitter-m", "tool:m-standard"],
                "verification_commands": ["make check", "m doctor"],
            },
        }
    }


@pytest.fixture
def task_index_with_recipes() -> dict:
    return {
        "categories": {
            "lib": {
                "json_parse": {
                    "intent": "Parse JSON text into an M tree",
                    "primary": "module:m-stdlib#STDJSON",
                }
            },
            "recipes": {
                "new_app_tdd_ci": {
                    "intent": "Scaffold a new M project with TDD + CI in 60 seconds",
                    "primary": "recipe:new-app-tdd-ci",
                    "doc": "https://github.com/m-dev-tools/.github/blob/main/docs/recipes/new-app-tdd-ci.md",
                }
            },
        }
    }


# ---- tool: --------------------------------------------------------------------


def test_describe_tool_returns_top_level_entry(tools: dict, task_index: dict) -> None:
    blob = describe_impl("tool:m-stdlib", tools, task_index)
    assert blob["typed_id"] == "tool:m-stdlib"
    assert blob["kind"] == "tool"
    assert blob["repo"] == "https://github.com/m-dev-tools/m-stdlib"
    # *_url pointers must surface verbatim.
    assert "modules_url" in blob
    assert "repo_meta_url" in blob


def test_describe_tool_missing_in_catalog_raises(task_index: dict) -> None:
    with pytest.raises(DiscoveryError) as exc_info:
        describe_impl("tool:does-not-exist", {"tools": {}}, task_index)
    assert exc_info.value.code == "tool_not_found"


# ---- module: ------------------------------------------------------------------


def test_describe_module_resolves_manifest_url(tools: dict, task_index: dict) -> None:
    blob = describe_impl("module:m-stdlib#STDJSON", tools, task_index)
    assert blob["typed_id"] == "module:m-stdlib#STDJSON"
    assert blob["kind"] == "module"
    assert blob["symbol"] == "STDJSON"
    assert blob["manifest_url"] == "file://./stdlib-manifest.json"
    # Parent tool pointer is included so the client can fetch
    # AGENTS.md / repo.meta.json in one round-trip.
    assert blob["tool"]["typed_id"] == "tool:m-stdlib"


def test_describe_module_without_member_raises(tools: dict, task_index: dict) -> None:
    with pytest.raises(DiscoveryError) as exc_info:
        describe_impl("module:m-stdlib", tools, task_index)
    assert exc_info.value.code == "typed_id_module_missing_member"


# ---- cmd: ---------------------------------------------------------------------


def test_describe_cmd_resolves_through_commands_url(
    tools_full: dict, task_index: dict
) -> None:
    blob = describe_impl("cmd:m-cli#test", tools_full, task_index)
    assert blob["typed_id"] == "cmd:m-cli#test"
    assert blob["kind"] == "cmd"
    assert blob["command"] == "test"
    assert blob["commands_url"] == (
        "https://raw.githubusercontent.com/m-dev-tools/m-cli/main/dist/commands.json"
    )
    assert blob["tool"]["typed_id"] == "tool:m-cli"


def test_describe_cmd_without_member_raises(tools_full: dict, task_index: dict) -> None:
    with pytest.raises(DiscoveryError) as exc_info:
        describe_impl("cmd:m-cli", tools_full, task_index)
    assert exc_info.value.code == "typed_id_cmd_missing_member"


# ---- recipe: ------------------------------------------------------------------


def test_describe_recipe_resolves_through_task_index(
    tools: dict, task_index_with_recipes: dict
) -> None:
    blob = describe_impl("recipe:new-app-tdd-ci", tools, task_index_with_recipes)
    assert blob["typed_id"] == "recipe:new-app-tdd-ci"
    assert blob["kind"] == "recipe"
    assert blob["html_url"].endswith("/docs/recipes/new-app-tdd-ci.md")
    assert blob["raw_url"].startswith("https://raw.githubusercontent.com/")
    assert blob["intent"] == "Scaffold a new M project with TDD + CI in 60 seconds"


def test_describe_recipe_not_in_catalog_raises(tools: dict, task_index_with_recipes: dict) -> None:
    with pytest.raises(DiscoveryError) as exc_info:
        describe_impl("recipe:does-not-exist", tools, task_index_with_recipes)
    assert exc_info.value.code == "recipe_not_found"


def test_describe_recipe_without_recipes_category_raises(tools: dict) -> None:
    """A task_index that pre-dates Phase 3 Track A (no ``recipes``
    category) must fail loudly — not silently return an empty blob."""
    with pytest.raises(DiscoveryError) as exc_info:
        describe_impl("recipe:new-app-tdd-ci", tools, {"categories": {}})
    assert exc_info.value.code == "recipes_category_missing"


# ---- grammar / kind errors ----------------------------------------------------


def test_describe_malformed_typed_id_raises(tools: dict, task_index: dict) -> None:
    with pytest.raises(DiscoveryError) as exc_info:
        describe_impl("not-a-typed-id", tools, task_index)
    assert exc_info.value.code == "typed_id_malformed"


def test_describe_unsupported_kind_raises(tools: dict, task_index: dict) -> None:
    """``rule:`` / ``doc:`` / etc. are valid typed-ID kinds in the
    grammar but not handled by this server. Surface a clear error so
    the client knows to ask for ``describe(typed_id)`` only on kinds
    we support."""
    # Use ``doc:`` — valid grammar (lowercase slug), but not one of the
    # four kinds describe() handles. ``rule:`` slugs in the wild are
    # uppercase (M-MOD-001) which fails the typed-ID grammar before the
    # kind check.
    with pytest.raises(DiscoveryError) as exc_info:
        describe_impl("doc:ai-discoverability-plan", tools, task_index)
    assert exc_info.value.code == "typed_id_kind_unsupported"
