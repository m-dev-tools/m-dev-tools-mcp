# Claude Code integration

Drop-in MCP-server config for [Claude Code](https://docs.claude.com/en/docs/claude-code). Once the server is registered, Claude can route plain-English questions about the m-dev-tools org ("how do I parse JSON in M?") through `route_intent` instead of guessing from training data.

## Install

Two paths, both work:

### 1. uvx (from git) — what `.mcp.json` here uses

No release needed; pins to `main`. Picks up new merges on every server restart.

```bash
uvx --from git+https://github.com/m-dev-tools/m-dev-tools-mcp@main m-dev-tools-mcp
```

### 2. Release wheel (Track D onward)

Once `v0.1.0` ships:

```bash
pip install https://github.com/m-dev-tools/m-dev-tools-mcp/releases/download/v0.1.0/m_dev_tools_mcp-0.1.0-py3-none-any.whl
m-dev-tools-mcp                       # boot the stdio MCP server
```

Pin to a tag (`@v0.1.0`) in your `.mcp.json` when stability matters.

## Register with Claude Code

Copy `.mcp.json` to your project root (or merge with your existing one). Claude Code auto-discovers MCP servers from `.mcp.json` in the working directory.

Sanity check:

```bash
claude --print "list your MCP tools"
# expected: route_intent, describe, verify
```

## Other MCP clients

The `.mcp.json` shape here is portable. Codex / Continue / any MCP-capable agent should accept the same `{ mcpServers: { <name>: { command, args } } }` structure — refer to each client's docs for the config file location. Phase 4 ships Claude Code as the gating client; other clients are documented as "should work" but unverified (phase4-plan.md §9 risk note).

## Smoke test — agent-free

Don't want to open Claude Code? `smoke.sh` shells the MCP server's `--tool` CLI surface directly and asserts the canonical query (`"parse JSON in M"` → `module:m-stdlib#STDJSON`):

```bash
./smoke.sh
# → 0/1 exit; stdout contains "module:m-stdlib#STDJSON"
```

The same canonical query plus the recorded Claude Code session live in `session.md` (template, replace placeholders after you run it locally).
