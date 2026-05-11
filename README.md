# m-dev-tools-mcp

MCP server for the [m-dev-tools](https://github.com/m-dev-tools) org catalog. Exposes three first-class agent tools:

- **`route_intent(query)`** — plain-English intent → typed IDs (e.g. `"parse JSON in M"` → `module:m-stdlib#STDJSON`)
- **`describe(typed_id)`** — typed ID → pointer-blob (manifest URL, `AGENTS.md` URL, verification commands, …)
- **`verify(repo)`** — list a repo's declared verification commands (does not execute them)

The server reads the catalog at <https://github.com/m-dev-tools/.github> over the network at call time; it is a thin wrapper, not a cache. See [`AGENTS.md`](https://github.com/m-dev-tools/m-dev-tools-mcp/blob/main/AGENTS.md) for the contract and the [AI users guide](https://github.com/m-dev-tools/.github/blob/main/docs/ai-discoverability/ai-users-guide.md) for the full walk-through.

<!-- Required by registry.modelcontextprotocol.io for PyPI ownership validation. Do not remove. -->
mcp-name: io.github.m-dev-tools/m-dev-tools-mcp

## Install

```bash
pip install m-dev-tools-mcp
# or:
uvx m-dev-tools-mcp
# or from a GitHub Release wheel:
pip install https://github.com/m-dev-tools/m-dev-tools-mcp/releases/download/v0.2.4/m_dev_tools_mcp-0.2.4-py3-none-any.whl
```

Point any MCP client at the `m-dev-tools-mcp` binary the install provides:

```json
{
  "mcpServers": {
    "m-dev-tools": { "command": "m-dev-tools-mcp" }
  }
}
```

Or for clients that consult the public MCP registry:

```
io.github.m-dev-tools/m-dev-tools-mcp
```

## Develop

```bash
make install        # creates .venv and installs editable + dev deps
make test           # pytest
make check          # lint + mypy + test + check-manifest + check-agents
make build          # → wheel-out/m_dev_tools_mcp-<ver>-py3-none-any.whl
```

## More

- Architecture: [m-dev-tools/.github](https://github.com/m-dev-tools/.github)'s `docs/ai-discoverability/AI-discoverability-architecture.md`
- Plan + phases: `docs/ai-discoverability/phases/`
- Release process: tag `vX.Y.Z` on `main` → `.github/workflows/release.yml` builds the wheel, attaches it to a GitHub Release, publishes to PyPI via Trusted Publisher OIDC, and updates the MCP registry record via GitHub OIDC.

## License

[AGPL-3.0](LICENSE). Same license as every other m-dev-tools repo.
