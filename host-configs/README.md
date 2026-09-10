# Agent configuration files

- Portable Agent Plugin and Codex: root `plugin.json`, `mcp.json`, and `skills/`
- Claude Code: `.claude-plugin/plugin.json`, root `.mcp.json`, and `skills/`
- Cursor: root Agent Plugin files plus `.cursor-plugin/plugin.json`
- OpenCode: merge `opencode.jsonc` into the project or user OpenCode config
- Hermes: merge `hermes.yaml` into `~/.hermes/config.yaml`
- Pi: see `pi.md`; the npm Extension bridges the local MCP server
- WorkBuddy/CodeBuddy: merge `workbuddy.json` into `~/.codebuddy/.mcp.json` or project `.mcp.json`

All supported MCP entries start the local command `omnischolar mcp`. These files contain no provider credentials.
