# 安装与 Agent 配置

[English](INSTALLATION.en.md)

## 安装 Python 命令

需要 Python 3.11 或更高版本，任选一种方式：

```sh
uv tool install luffysolution-omnischolar
pipx install luffysolution-omnischolar
python -m pip install luffysolution-omnischolar
```

如需从源码开发安装，请将包名替换为 `.`。

验证命令是否可用：

```sh
omnischolar --version
omnischolar doctor --json
```

如果采用下面的 Codex 插件安装方式，则无需预先安装上述 Python 命令；插件会通过 `uvx` 运行固定版本的 PyPI 包。

## 安装到 Codex App 或 Codex CLI

本仓库本身就是 Codex Git Marketplace。先安装 [`uv`](https://docs.astral.sh/uv/getting-started/installation/)，并确认两个命令可用：

```sh
codex --version
uv --version
```

添加 Marketplace 并安装 OmniScholar：

```sh
codex plugin marketplace add luffysolution-svg/omnischolar --ref main
codex plugin add omnischolar@omnischolar
```

添加 Marketplace 后请重启 ChatGPT 桌面应用，打开 **Plugins**，切换到 **OmniScholar** 来源，再安装或启用插件。Codex CLI 用户可以运行 `/plugins` 并选择同一条目。

安装后的插件包含 `plugin.json`、`skills/` 和 `mcp.json`。其 MCP 配置执行：

```sh
uvx --from luffysolution-omnischolar==0.1.0 omnischolar mcp
```

`uvx` 会创建隔离环境并缓存该精确版本，因此无需另行运行 `pip install`。第一次启动需要能够访问 Python 包索引。若要更新 Git Marketplace：

```sh
codex plugin marketplace upgrade omnischolar
```

卸载插件或移除 Marketplace 来源：

```sh
codex plugin remove omnischolar@omnischolar
codex plugin marketplace remove omnischolar
```

只有在已卸载其中插件后才建议移除 Marketplace 来源。

## 安装本地 MCP 与 Skills

```sh
omnischolar install --dry-run claude
omnischolar install claude
```

`--dry-run` 只显示计划，不写文件。默认安装到当前用户；项目级配置使用 `--scope project`：

```sh
omnischolar install cursor --scope project
```

| Agent | 用户级 MCP | 项目级 MCP | Skills |
|---|---|---|---|
| Codex | `~/.codex/config.toml` | `.codex/config.toml` | 支持 |
| Claude Code | `~/.claude.json` | `.mcp.json` | 支持 |
| Cursor | `~/.cursor/mcp.json` | `.cursor/mcp.json` | 支持 |
| OpenCode | `~/.config/opencode/opencode.json` | `opencode.jsonc` | 支持 |
| Hermes | `~/.hermes/config.yaml` | 需手动设置 MCP | 支持 |
| Pi | npm Extension | npm Extension | 支持 |
| WorkBuddy/CodeBuddy | `~/.codebuddy/.mcp.json` | `.mcp.json` | 无官方可移植目录 |

对 Pi，`omnischolar install pi` 会通过 Pi 包管理器安装 `npm:@luffysolution/omnischolar-pi`，并把 Skills 复制到所选作用域。Extension 会启动本地 `omnischolar mcp` 进程，因此 `pi` 与 Python 的 `omnischolar` 命令都必须位于 `PATH`。

WorkBuddy/CodeBuddy 支持本地 stdio MCP。其官方文档没有定义可移植的 Skills 目录，因此安装器只自动配置 MCP。

## 更新、卸载与恢复

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

修改前会创建备份。若安装后的 MCP 握手失败，原配置会自动恢复。也可手动恢复命令返回的备份：

```sh
omnischolar rollback PATH_TO_BACKUP
```

已有的其他 MCP 服务和 Skills 不会被删除。若同名配置不属于 OmniScholar，或已安装的 Skill 被手工改过，命令会停止并说明冲突。

## 使用官方 Skills CLI

Skills CLI 与 Python/MCP 安装相互独立。先查看适合目标 Agent 的命令：

```sh
omnischolar npx-skills cursor
```

例如：

```sh
npx skills add luffysolution-svg/omnischolar --skill '*' -a cursor -y
npx skills update -p -y
```

这组命令只安装 Skills，不会安装 `omnischolar` Python 命令。

## MCP 连接失败

1. 运行 `omnischolar --version`，确认 Agent 的 PATH 能找到该命令。
2. 运行 `omnischolar mcp status HOST` 查看安装位置。
3. 运行 `omnischolar doctor --json` 检查配置和输出目录。
4. 重启 Agent，再查看其 MCP 日志。
5. 若需重新安装，先运行 `omnischolar install --dry-run HOST`。

OmniScholar 的 MCP 入口只有本地 stdio：

```sh
omnischolar mcp
```
