---
# Machine-readable project descriptor.
name: m-dev-tools-mcp
kind: [mcp-server, agent-tooling]
status: scaffold
languages: [python]

runtime:
  needs:
    - python>=3.10
    - "mcp>=1.2 (the official MCP Python SDK; pinned in pyproject.toml)"
  optional:
    - "no engine dependency — this server only reads the m-dev-tools catalog over HTTP"
  excludes: []

distribution:
  pypi: null                                 # GitHub Releases only (phase4-plan.md §0)
  github: m-dev-tools/m-dev-tools-mcp

location: ~/m-dev-tools/m-dev-tools-mcp

exposes:
  mcp_tools:
    - route_intent(query)                    # plain-English intent → typed IDs
    - describe(typed_id)                     # typed ID → pointer-blob (manifest URL, AGENTS.md URL, …)
    - verify(repo)                           # list a repo's declared verification commands (no exec)

consumes:
  - tool:m-cli                               # routing-trail target
  - tool:m-stdlib                            # routing-trail target
  - tool:m-standard                          # routing-trail target
  - tool:tree-sitter-m
  - tool:m-test-engine
  - tool:m-modern-corpus
---

# m-dev-tools-mcp — agent-facing notes

The frontmatter above is the canonical machine-readable surface. Below
is human prose for agents (and humans) operating in this repo.

`CLAUDE.md` is a symlink to this file — single source of truth.

## Role

This repo packages a thin MCP server that wraps the
[`m-dev-tools` org catalog](https://github.com/m-dev-tools/.github/blob/main/profile/tools.json)
as a first-class protocol surface. Three MCP tools are registered:

| Tool | Purpose |
|---|---|
| `route_intent(query)` | Plain-English intent → typed IDs. Example: `"parse JSON in M"` → `["module:m-stdlib#STDJSON"]`. |
| `describe(typed_id)` | Typed ID → pointer-blob with `manifest_url`, `agent_instructions`, `verification_commands`. Does **not** inline payloads — keeps the catalog's "pointers, not facts" invariant. |
| `verify(repo)` | Return the `verification_commands` declared in a repo's `dist/repo.meta.json`. **Does not execute them** — that is a client decision (see Track B §3 B5 rationale in [phase4-plan.md](https://github.com/m-dev-tools/.github/blob/main/docs/phase4-plan.md)). |

Distribution is GitHub-Release wheels, not PyPI (`phase4-plan.md` §0).
Install via `uvx --from git+https://github.com/m-dev-tools/m-dev-tools-mcp@v<X.Y> m-dev-tools-mcp`.

## Status

**Track A** (this scaffold): repo skeleton + Phase-0 contract + CI. Tool
bodies raise `NotImplementedError`. **Track B** lands real behavior.
**Tracks C / D / E** add Claude Code integration smoke, the v0.1.0
release wheel, and Phase 4 exit evidence.

## Setup

```bash
make install        # python3 -m venv .venv; .venv/bin/pip install -e ".[dev]"
```

A working `python3.10+` is the only host prerequisite. No engine; no
network at install time beyond PyPI for the MCP SDK + dev deps.

## Test

```bash
make test           # .venv/bin/pytest tests/
```

Track B's TDD suites land as `tests/test_route_intent.py` /
`test_describe.py` / `test_verify.py`. Track A ships `tests/test_smoke.py`
only.

## Verify

```bash
make check          # lint + mypy + test + check-manifest + check-agents
```

`make check` is what CI runs on every push and pull request. It is the
contract every commit must satisfy.

## Guardrails

- **`AGENTS.md` is the single source of truth for agent instructions.**
  `CLAUDE.md` is a symlink to it. Edit AGENTS.md, never CLAUDE.md.
- **`dist/repo.meta.json` validates against the org-level schema** at
  <https://raw.githubusercontent.com/m-dev-tools/.github/main/profile/repo.meta.schema.json>.
  The meta-repo's `make check-repo-meta META=…` is the org-side gate.
- **`dist/mcp-tools.json` is generated**, not hand-edited. `make manifest`
  is the regen; `make check-manifest` is the drift gate that CI runs.
- **Tool stubs raise `NotImplementedError`.** A Track-B PR replacing a
  stub with real behavior must also delete the matching
  `test_tool_stubs_raise_not_implemented` case in `tests/test_smoke.py`
  (the test pins Track A's contract; Track B intentionally retires it).
- **No catalog state is cached on disk.** The MCP server fetches
  `tools.json` + `task_index.json` from `origin/main` over HTTPS at call
  time. A 60-second in-memory cache lives inside the process; nothing
  hits the filesystem.
- **`verify` lists commands; it does not execute them.** Executing
  catalog-derived commands is the client's decision (the agent, with the
  user's consent). Documented in this AGENTS.md so future sessions
  don't silently re-widen the contract.

## Layout conventions

Mirrors the org-wide convention (see m-cli / m-stdlib / m-standard).

```
m-dev-tools-mcp/
├── AGENTS.md                       # ← single source of truth (this file)
├── CLAUDE.md                       # symlink → AGENTS.md
├── LICENSE                         # AGPL-3.0
├── Makefile                        # uses .venv/bin/ prefixes everywhere
├── README.md
├── pyproject.toml                  # mcp SDK pinned; dev extras: pytest, ruff, mypy
├── .github/
│   └── workflows/ci.yml            # runs `make check` on push + PR
├── dist/
│   ├── repo.meta.json              # tracked — org-level validator reads this
│   └── mcp-tools.json              # tracked — generated by `make manifest`
├── scripts/
│   └── gen-mcp-tools-manifest.py   # introspects @server.tool() decorators
├── src/
│   └── m_dev_tools_mcp/
│       ├── __init__.py             # __version__
│       ├── __main__.py             # console entry point
│       └── server.py               # build_server() + 3 @server.tool() defs
└── tests/
    ├── __init__.py
    ├── test_smoke.py               # Track A
    └── test_<tool>.py              # Track B (one file per tool, TDD)
```

`docs/` holds only human-readable prose (same org-wide rule the
meta-repo's `make check-docs-prose` enforces). Generated artifacts live
under `dist/` or `scripts/`.

## Library API for tooling consumers

Importable from `m_dev_tools_mcp.server`:

| Symbol | Track | Purpose |
|---|---|---|
| `build_server()` | A | Construct and return a configured `FastMCP` instance with three tools registered. Importable; does **not** start the event loop. |
| `route_intent` | B (B2) | Stub in A. Returns `list[str]` of typed IDs in B. |
| `describe` | B (B4) | Stub in A. Returns `dict[str, Any]` pointer-blob in B. |
| `verify` | B (B5) | Stub in A. Returns `list[str]` of verification commands in B. |

Track B vendors a subset of Phase 3's discovery helpers from
`.github`'s `profile/build/test-discovery-protocol.py` — see Track B
§3 in [phase4-plan.md](https://github.com/m-dev-tools/.github/blob/main/docs/phase4-plan.md)
for the vendoring rationale.

## Git conventions

- Single squash-merge per PR. PR titles use the `phase4-<track>:` prefix
  for plan-aligned work; `chore:` / `docs:` / `fix:` for everything else.
- Never hand-edit `dist/mcp-tools.json`. The drift gate will flag it.
- Don't push to `main` directly. Branch + PR + CI green + squash-merge.

## Claude guidelines

When acting in this repo, Claude should:

1. Read this AGENTS.md once per fresh session.
2. Treat `make check` as the contract — don't claim a stage complete
   without it green.
3. Defer to [phase4-plan.md](https://github.com/m-dev-tools/.github/blob/main/docs/phase4-plan.md)
   for stage shape and verification commands; it is the load-bearing
   plan document for this repo's whole lifecycle.
4. Follow TDD strictly: tests first, confirm RED, implement, confirm
   GREEN. Same hard rule as the rest of the m-dev-tools org.
5. Prefer importing or vendoring small pure functions from the meta-repo
   over reimplementing them. The meta-repo is not a Python package; copy
   under `_discovery.py` (Track B) and pin behavior in this repo's TDD
   suite.
