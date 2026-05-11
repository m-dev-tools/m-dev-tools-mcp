.PHONY: install test lint mypy fmt check manifest check-manifest check-agents clean

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF   := .venv/bin/ruff
MYPY   := .venv/bin/mypy

# Sources that drive dist/mcp-tools.json. Only server.py introspection
# feeds the manifest, but bumping the package version invalidates the
# header too — list both so `make manifest` re-runs on any version bump.
MANIFEST_SOURCES := src/m_dev_tools_mcp/server.py src/m_dev_tools_mcp/__init__.py

install:
	@test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTEST) tests/

lint:
	$(RUFF) check src/ tests/ scripts/

fmt:
	$(RUFF) format src/ tests/ scripts/
	$(RUFF) check --fix src/ tests/ scripts/

mypy:
	$(MYPY) src/m_dev_tools_mcp

# `make check` is what CI runs. Mirrors the m-cli convention:
# format-check, lint, mypy, tests, plus the two drift gates that keep
# the dist/ manifests honest.
check: lint mypy test check-manifest check-agents

# Regenerate dist/mcp-tools.json by introspecting server.py's
# @mcp.tool decorators. Idempotent — running twice produces byte-
# identical output.
manifest:
	$(PYTHON) scripts/gen-mcp-tools-manifest.py --write dist/mcp-tools.json

# Drift gate: regenerate, then `git diff --exit-code`. Same pattern
# every tier-1 / tier-2 / tier-3 repo uses. Fails fast if a contributor
# hand-edited dist/mcp-tools.json or forgot to run `make manifest`
# after editing server.py.
check-manifest: manifest
	@git diff --exit-code dist/mcp-tools.json \
	    || { echo "ERROR: dist/mcp-tools.json drift — run 'make manifest' and commit." >&2; exit 1; }
	@echo "check-manifest: clean"

# Cross-repo guardrail: AGENTS.md exists, and CLAUDE.md is a symlink
# to it (single-source-of-truth for agent instructions). Same shape as
# every other m-dev-tools repo's check-agents target.
check-agents:
	@test -f AGENTS.md || { echo "ERROR: AGENTS.md missing" >&2; exit 1; }
	@test -L CLAUDE.md || { echo "ERROR: CLAUDE.md must be a symlink to AGENTS.md" >&2; exit 1; }
	@target=$$(readlink CLAUDE.md); \
	  if [ "$$target" != "AGENTS.md" ]; then \
	    echo "ERROR: CLAUDE.md → $$target; expected AGENTS.md" >&2; exit 1; \
	  fi
	@echo "check-agents: AGENTS.md present; CLAUDE.md → AGENTS.md ✓"

clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache build dist/*.egg-info \
	    src/*.egg-info
