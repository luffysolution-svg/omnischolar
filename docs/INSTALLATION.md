# 安装与 Agent 配置

[English](INSTALLATION.en.md)

## 安装 Python 命令

需要 Python 3.11 或更高版本，任选一种方式：

```sh
uv tool install luffysolution-omnischolar
pipx install luffysolution-omnischolar
python -m pip install luffysolution-omnischolar
```

如果该工具已经安装，`uv tool install` 会保持现有版本，不会自动升级。要获取 PyPI 最新版本，请使用：

```sh
uv tool upgrade luffysolution-omnischolar
```

需要强制刷新并重新安装时使用：

```sh
uv tool install --reinstall luffysolution-omnischolar
```

更新或卸载 Python 命令：

```sh
uv tool upgrade luffysolution-omnischolar
uv tool uninstall luffysolution-omnischolar
```

若最初使用 `pipx` 或 `pip`，对应的更新和卸载命令是：

```sh
pipx upgrade luffysolution-omnischolar
pipx uninstall luffysolution-omnischolar
python -m pip install --upgrade luffysolution-omnischolar
python -m pip uninstall luffysolution-omnischolar
```

如需从源码开发安装，请将包名替换为 `.`。

验证命令是否可用：

```sh
omnischolar --version
omnischolar doctor --json
```

如果采用下面的 Codex 插件安装方式，则无需预先安装上述 Python 命令；插件会通过 `uvx` 运行 PyPI 最新包。

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
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```

`uvx` 会创建隔离环境，并在每次启动时刷新包缓存后运行 PyPI 最新包，无需另行运行 `pip install`。

若要更新 Codex Git Marketplace 和插件：

```sh
codex plugin marketplace upgrade omnischolar
codex plugin remove omnischolar@omnischolar
codex plugin add omnischolar@omnischolar
```

卸载插件或移除 Marketplace 来源：

```sh
codex plugin remove omnischolar@omnischolar
codex plugin marketplace remove omnischolar
```

只有在已卸载其中插件后才建议移除 Marketplace 来源。

## 安装到 Claude Code

先安装 [`uv`](https://docs.astral.sh/uv/getting-started/installation/)。在 Claude Code 交互会话中运行：

```text
/plugin marketplace add luffysolution-svg/omnischolar
/plugin install omnischolar@omnischolar
```

在脚本或非交互式环境中可使用 shell 命令：

```sh
claude plugin marketplace add luffysolution-svg/omnischolar
claude plugin install omnischolar@omnischolar --scope user
```

使用 `--scope project` 可通过仓库设置与协作者共享启用状态；使用 `--scope local` 则只在当前仓库为自己启用。如果 Claude 提示 `Run /reload-plugins to activate`，请先运行该命令。

Claude Code 会把仓库根插件复制到版本化缓存，发现 `skills/` 下的 9 个 Skills，并在插件启用时自动启动 `.mcp.json`。MCP 命令使用 PyPI 最新包：

```sh
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```

第一次启动 MCP 需要能够访问 Python 包索引。Skills 使用 `omnischolar` 命名空间，例如 `/omnischolar:scholar-search` 和 `/omnischolar:zotero-research`。

更新或移除安装：

```sh
claude plugin marketplace update omnischolar
claude plugin update omnischolar@omnischolar --scope user
claude plugin uninstall omnischolar@omnischolar --scope user
claude plugin marketplace remove omnischolar
```

请在卸载来自该 Marketplace 的插件后再移除 Marketplace。

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

对 Pi，`omnischolar install pi` 会通过 Pi 包管理器安装最新的 `npm:@luffysolution/omnischolar-pi`，并把 Skills 复制到所选作用域。Extension 会通过 `uvx` 启动 PyPI 最新 MCP，因此只需保证 `uv` 位于 `PATH`，无需另行安装全局 Python 命令。直接管理 Pi Extension 时使用：

```sh
pi install npm:@luffysolution/omnischolar-pi
pi update npm:@luffysolution/omnischolar-pi
pi remove npm:@luffysolution/omnischolar-pi
```

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
# 用户级安装：将 codex 替换为 claude-code、pi、cursor 或其他受支持 Agent
npx skills add luffysolution-svg/omnischolar --skill '*' -a codex -g -y
npx skills update -g -y
npx skills remove --skill '*' -a codex -g -y

# 项目级安装：省略 -g；更新和卸载也使用项目作用域
npx skills add luffysolution-svg/omnischolar --skill '*' -a codex -y
npx skills update -p -y
npx skills remove --skill '*' -a codex -y
```

这组命令只安装 Skills，不会安装 `omnischolar` Python 命令。通过 Codex/Claude plugin 或 Pi Extension 安装时，插件/安装器已经处理了对应 Skills，不需要重复执行。

## Agent 配置提示词

可以将下面的提示词作为 Agent 的项目级指令或系统提示词基础：

```text
你是我的科研助理，使用 OmniScholar 完成文献检索、Zotero 阅读、PDF 解析、引用核对和科研资料整理。检索时优先使用可靠的学术来源，核对 DOI 与书目信息，并明确区分原文证据、推断和不确定内容。Zotero 只允许读取，禁止修改。上传 PDF、参考图或发起可能收费的请求前必须先征得我的确认；MinerU 只有在我确认后才能上传文件。将确认后的文献笔记和生成文件保存到配置的输出目录，保留已有手工修改，并报告最终文件路径。生成的科研图片只能作为示意图，不能当作实验数据或科研证据。
```

## MCP 连接失败

1. 运行 `omnischolar --version`，确认 Agent 的 PATH 能找到该命令。
2. 运行 `omnischolar mcp status HOST` 查看安装位置。
3. 运行 `omnischolar doctor --json` 检查配置和输出目录。
4. 重启 Agent，再查看其 MCP 日志。
5. 若需重新安装，先运行 `omnischolar install --dry-run HOST`。

OmniScholar 的 MCP 入口只有本地 stdio：

```sh
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```
