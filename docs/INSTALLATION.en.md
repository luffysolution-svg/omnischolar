# Installation and agent setup

[简体中文](INSTALLATION.md)

## Install the Python command

Python 3.11 or newer is required. Choose one installer:

```sh
uv tool install luffysolution-omnischolar
pipx install luffysolution-omnischolar
python -m pip install luffysolution-omnischolar
```

For development from a source checkout, replace the package name with `.`.

Check the command:

```sh
omnischolar --version
omnischolar doctor --json
```

## Install local MCP and Skills

```sh
omnischolar install --dry-run claude
omnischolar install claude
```

`--dry-run` prints the planned changes without writing files. User scope is the default; use `--scope project` for repository-local configuration:

```sh
omnischolar install cursor --scope project
```

| Agent | User MCP | Project MCP | Skills |
|---|---|---|---|
| Codex | `~/.codex/config.toml` | `.codex/config.toml` | supported |
| Claude Code | `~/.claude.json` | `.mcp.json` | supported |
| Cursor | `~/.cursor/mcp.json` | `.cursor/mcp.json` | supported |
| OpenCode | `~/.config/opencode/opencode.json` | `opencode.jsonc` | supported |
| Hermes | `~/.hermes/config.yaml` | manual MCP setup | supported |
| Pi | npm Extension | npm Extension | supported |
| WorkBuddy/CodeBuddy | `~/.codebuddy/.mcp.json` | `.mcp.json` | no documented portable path |

For Pi, `omnischolar install pi` installs `npm:@luffysolution/omnischolar-pi` with Pi's package manager and copies the Skills to the selected scope. The Extension starts the local `omnischolar mcp` process. The `pi` command and the Python `omnischolar` command must both be on `PATH`.

WorkBuddy/CodeBuddy supports local stdio MCP servers. Its official documentation does not define a portable Skills directory, so only the MCP component is installed automatically.

## Update, uninstall, and restore

```sh
omnischolar update claude
omnischolar uninstall claude

omnischolar mcp install claude
omnischolar mcp status claude
omnischolar mcp uninstall claude

omnischolar install skills claude
omnischolar update skills claude
omnischolar uninstall skills claude

omnischolar update pi
omnischolar uninstall pi
```

A backup is created before each change. If the MCP handshake fails after installation, the previous configuration is restored automatically. To restore a reported backup yourself:

```sh
omnischolar rollback PATH_TO_BACKUP
```

Other MCP servers and Skills are left in place. The command stops if an existing `omnischolar` entry was not created by this installer or if a managed Skill was edited locally.

## Use the official Skills CLI

The Skills CLI is separate from Python and MCP installation. Print the command for an agent with:

```sh
omnischolar npx-skills cursor
```

For example:

```sh
npx skills add luffysolution-svg/omnischolar --skill '*' -a cursor -y
npx skills update -p -y
```

These commands install Skills only; they do not install the `omnischolar` Python command.

## If MCP does not connect

1. Run `omnischolar --version` from the environment used by the agent.
2. Run `omnischolar mcp status HOST` to inspect the installed path.
3. Run `omnischolar doctor --json` to check configuration and output access.
4. Restart the agent and inspect its MCP log.
5. Before reinstalling, run `omnischolar install --dry-run HOST`.

The only MCP server entry in this release is local stdio:

```sh
omnischolar mcp
```
