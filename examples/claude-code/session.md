# Claude Code session transcript (template)

> **Status: TEMPLATE — needs to be filled in once with a real session.**
>
> Phase 4 Track C (per [phase4-plan.md §4 C3](https://github.com/m-dev-tools/.github/blob/main/docs/ai-discoverability/phase4-plan.md))
> calls for a recorded session that proves Claude Code routes the
> canonical question through this MCP server's `route_intent` tool —
> not by guessing from training data. The session can't be auto-
> recorded from inside Claude Code itself, so the steps below
> describe what to do. Replace the placeholder spans (`<<< … >>>`)
> with the real output once you've run the session locally, then
> commit the filled-in version.

## How to record a session

1. **Install Claude Code** if you haven't: <https://docs.claude.com/en/docs/claude-code/>.
2. **Register this MCP server.** Copy `examples/claude-code/.mcp.json` (sibling of this file) into the project root, or merge it into your existing `.mcp.json`.
3. **Open Claude Code** in this repo:

   ```bash
   cd ~/m-dev-tools/m-dev-tools-mcp
   claude
   ```

4. **Confirm the server is registered.** At the prompt:

   ```
   list your MCP tools
   ```

   You should see `route_intent`, `describe`, and `verify` in the response.

5. **Ask the canonical question:**

   ```
   How do I parse JSON in M?
   ```

   Claude should:

   - Call `route_intent("parse JSON in M")` (visible in the session's tool-use trace).
   - Receive `["module:m-stdlib#STDJSON"]`.
   - Optionally call `describe("module:m-stdlib#STDJSON")` to follow the manifest URL pointer.
   - Compose an answer that references `parse^STDJSON` from m-stdlib.

6. **Copy the session trace** (Claude Code's `--print` or the trace panel) into the section below, replacing the placeholder spans.

## Recorded session

**Date:** <<<2026-MM-DD>>>
**Claude Code version:** <<<output of `claude --version`>>>
**MCP server version:** <<<output of `m-dev-tools-mcp --version`>>>

### Tool list

```
<<< paste response to "list your MCP tools" >>>
```

### Canonical question

> How do I parse JSON in M?

### Tool-use trace

<details>
<summary>route_intent("parse JSON in M")</summary>

```json
<<< paste the route_intent response — should contain "module:m-stdlib#STDJSON" >>>
```

</details>

<details>
<summary>describe("module:m-stdlib#STDJSON") — if Claude followed the pointer</summary>

```json
<<< paste the describe response — should contain manifest_url and tool.repo >>>
```

</details>

### Final answer

```
<<< paste Claude's final answer to the user; it should reference parse^STDJSON >>>
```

### Verification

- [ ] `route_intent` was called (not Claude guessing from training).
- [ ] The response contained `module:m-stdlib#STDJSON`.
- [ ] The answer named `parse^STDJSON` (the actual m-stdlib symbol).

## Falling back to `smoke.sh`

For CI / scripted verification (no real Claude Code session), `smoke.sh` exits 0 when the same canonical query resolves through the MCP server's CLI surface. That's the always-on assertion; this session.md is the once-per-release human-eyes confirmation.
