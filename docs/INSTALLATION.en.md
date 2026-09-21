# Installation and agent setup

[简体中文](INSTALLATION.md)

## Install the Python command

Python 3.11 or newer is required. Choose one installer:

```sh
uv tool install luffysolution-omnischolar
pipx install luffysolution-omnischolar
python -m pip install luffysolution-omnischolar
```

If the tool is already installed, `uv tool install` keeps the existing version instead of upgrading it. Use this command to get the latest PyPI release:

```sh
uv tool upgrade luffysolution-omnischolar
```

To force a cache refresh and reinstall the latest compatible release:

```sh
uv tool install --reinstall luffysolution-omnischolar
```

Update or uninstall the Python command:

```sh
uv tool upgrade luffysolution-omnischolar
uv tool uninstall luffysolution-omnischolar
```

If you originally installed with `pipx` or `pip`, use the matching update and uninstall commands:

```sh
pipx upgrade luffysolution-omnischolar
pipx uninstall luffysolution-omnischolar
python -m pip install --upgrade luffysolution-omnischolar
python -m pip uninstall luffysolution-omnischolar
```

For development from a source checkout, replace the package name with `.`.

Check the command:

```sh
omnischolar --version
omnischolar doctor --json
```

The Python command installation above is optional when you use the Codex plugin path below. The plugin runs the latest PyPI package through `uvx` instead.

## Install in the Codex app or Codex CLI

This repository is a Codex Git marketplace. Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and verify that both commands are available:

```sh
codex --version
uv --version
```

Add the marketplace and install OmniScholar:

```sh
codex plugin marketplace add luffysolution-svg/omnischolar --ref main
codex plugin add omnischolar@omnischolar
```

Restart the ChatGPT desktop app after adding the marketplace. Open **Plugins**, switch to the **OmniScholar** source, and install or enable the plugin. Codex CLI users can run `/plugins` and choose the same entry.

The installed plugin contains `plugin.json`, `skills/`, and `mcp.json`. Its MCP entry executes:

```sh
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```

`uvx` creates an isolated environment, refreshes the package cache on every start, and runs the latest PyPI package, so this route does not require a separate `pip install`.

To update the Codex Git marketplace and plugin, run:

```sh
codex plugin marketplace upgrade omnischolar
codex plugin remove omnischolar@omnischolar
codex plugin add omnischolar@omnischolar
```

To uninstall the plugin or remove its marketplace source:

```sh
codex plugin remove omnischolar@omnischolar
codex plugin marketplace remove omnischolar
```

Removing the marketplace is optional and should be done only after removing plugins installed from it.

## Install in Claude Code

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first. From an interactive Claude Code session, run:

```text
/plugin marketplace add luffysolution-svg/omnischolar
/plugin install omnischolar@omnischolar
```

Or use the shell commands for scripting and non-interactive setup:

```sh
claude plugin marketplace add luffysolution-svg/omnischolar
claude plugin install omnischolar@omnischolar --scope user
```

Choose `--scope project` to share the enabled plugin through repository settings, or `--scope local` to enable it only for yourself in the current repository. If Claude reports `Run /reload-plugins to activate`, run that command before using the plugin.

Claude Code copies the repository-root plugin into its versioned cache, discovers the nine folders under `skills/`, and starts `.mcp.json` automatically when the plugin is enabled. The MCP command uses the latest PyPI package:

```sh
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```

The first MCP start needs package-index access. Skills are namespaced with `omnischolar`, for example `/omnischolar:scholar-search` and `/omnischolar:zotero-research`.

Update or remove the installation with:

```sh
claude plugin marketplace update omnischolar
claude plugin update omnischolar@omnischolar --scope user
claude plugin uninstall omnischolar@omnischolar --scope user
claude plugin marketplace remove omnischolar
```

Remove the marketplace only after uninstalling plugins that came from it.

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

For Pi, `omnischolar install pi` installs the latest `npm:@luffysolution/omnischolar-pi` with Pi's package manager and copies the Skills to the selected scope. The Extension starts the latest PyPI MCP through `uvx`, so only `uv` must be on `PATH`; a separate global Python CLI installation is not required. To manage the Pi Extension directly:

```sh
pi install npm:@luffysolution/omnischolar-pi
pi update npm:@luffysolution/omnischolar-pi
pi remove npm:@luffysolution/omnischolar-pi
```

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

Other MCP servers and non-OmniScholar Skills are left in place. During an update, a previously managed Skill that is no longer bundled is backed up and removed. The command stops if an existing `omnischolar` entry was not created by this installer or if a managed Skill was edited locally.

## Use the official Skills CLI

The Skills CLI is separate from Python and MCP installation. Print the command for an agent with:

```sh
omnischolar npx-skills cursor
```

For example:

```sh
# User scope: replace codex with claude-code, pi, cursor, or another supported agent
npx skills add luffysolution-svg/omnischolar --skill '*' -a codex -g -y
npx skills update -g -y
npx skills remove --skill '*' -a codex -g -y

# Project scope: omit -g; use project scope for update and removal too
npx skills add luffysolution-svg/omnischolar --skill '*' -a codex -y
npx skills update -p -y
npx skills remove --skill '*' -a codex -y
```

These commands install Skills only; they do not install the `omnischolar` Python command. The Codex/Claude plugin or Pi full installer already handles its corresponding Skills, so do not install the same Skills twice.

## If MCP does not connect

1. Run `omnischolar --version` from the environment used by the agent.
2. Run `omnischolar mcp status HOST` to inspect the installed path.
3. Run `omnischolar doctor --json` to check configuration and output access.
4. Restart the agent and inspect its MCP log.
5. Before reinstalling, run `omnischolar install --dry-run HOST`.

The only MCP server entry in this release is local stdio:

```sh
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```
