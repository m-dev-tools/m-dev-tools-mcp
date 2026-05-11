# m-dev-tools-mcp

MCP server for the [m-dev-tools](https://github.com/m-dev-tools) org catalog. Exposes three first-class agent tools:

- **`route_intent(query)`** — plain-English intent → typed IDs (e.g. `"parse JSON in M"` → `module:m-stdlib#STDJSON`)
- **`describe(typed_id)`** — typed ID → pointer-blob (manifest URL, AGENTS.md URL, verification commands, …)
- **`verify(repo)`** — list a repo's declared verification commands (does not execute them)

The server reads the catalog at <https://github.com/m-dev-tools/.github> over the network at call time; it is a thin wrapper, not a cache. See [`AGENTS.md`](AGENTS.md) for the contract and [phase4-plan.md](https://github.com/m-dev-tools/.github/blob/main/docs/ai-discoverability/phase4-plan.md) for the broader plan.

## Status

Track A scaffold (Phase-0 contract + CI). The three tools are registered with the MCP framework but their bodies raise `NotImplementedError` until Track B lands. Distribution is GitHub Releases (not PyPI) per `phase4-plan.md` §0.

## Install (Track B onward)

```bash
uvx --from git+https://github.com/m-dev-tools/m-dev-tools-mcp@main m-dev-tools-mcp
```

## Develop

```bash
make install        # creates .venv and installs editable + dev deps
make test           # pytest
make check          # lint + mypy + test + check-manifest + check-agents
```

## License

[AGPL-3.0](LICENSE). Same license as every other m-dev-tools repo.
