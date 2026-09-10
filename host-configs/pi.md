# Pi

OmniScholar uses the npm-published `@luffysolution/omnischolar-pi` Extension to bridge its local MCP server into Pi. The full installer also copies Skills to `.pi/agent/skills` for user scope or `.pi/skills` for project scope.

```sh
omnischolar install pi
# or install only the Extension with Pi's package manager
pi install npm:@luffysolution/omnischolar-pi
```

The Extension starts `omnischolar mcp`, discovers the server's tools, forwards calls and cancellation signals, and closes the MCP client when the Pi session ends.

`omnischolar mcp install pi` remains `manual_required` because Pi uses an Extension instead of a native MCP settings file. Use the full `omnischolar install pi` command.
