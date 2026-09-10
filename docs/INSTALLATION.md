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
