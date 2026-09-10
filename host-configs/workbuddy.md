# Tencent WorkBuddy / CodeBuddy

WorkBuddy/CodeBuddy CLI and IDE support local stdio MCP servers. Copy [`workbuddy.json`](workbuddy.json) into the MCP editor, or merge it into one of the documented files:

- User scope: `~/.codebuddy/.mcp.json`
- Project scope: `.mcp.json`

The installer can write the same entry:

```sh
omnischolar install workbuddy
omnischolar install workbuddy --scope project
```

The official documentation does not define a portable WorkBuddy Skills directory, so the Skills component remains manual.

Official references checked on 2026-09-10:

- <https://www.workbuddy.ai/docs/cli/mcp>
- <https://www.workbuddy.ai/docs/ide/User-guide/MCP>
