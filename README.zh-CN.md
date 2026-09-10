# OmniScholar

[English](README.md) | 简体中文

OmniScholar 通过本地 Python MCP 服务，为 Codex、Claude Code、Cursor、OpenCode、Hermes 和 Pi 等 Agent 提供文献检索、Zotero 读取、PDF 解析、引用处理、材料数据和科研绘图工具。

它可以把在线文献记录与 Zotero 笔记放在一起处理，将经你确认的 PDF 交给 MinerU 解析，再把 Markdown 保存到普通文件夹或 Obsidian Vault。Zotero 全程只读。

## 功能

- 检索 Semantic Scholar、OpenAlex、PubMed/PMC、arXiv、Crossref、Unpaywall、easyScholar、Google Scholar 和 Google Patents
- 查询论文详情、作者、参考文献、施引文献、推荐、全文片段、数据集和期刊指标
- 读取 Zotero 收藏夹、条目、笔记、批注、附件、索引文本和本地 PDF 路径，不修改文献库
- 使用 MinerU 提取指定 PDF 的正文、公式、表格和图片
- 查找引用候选，核对书目信息，再按要求生成参考文献
- 查询 Materials Project，并导出 JSON、CSV、Markdown 或 CIF
- 调用已配置的图片服务生成或编辑科研示意图
- 保留手工修改过的 Markdown，把待合并版本放入 `.conflicts/`

OmniScholar 共提供 38 个工具，完整列表见[工具目录](docs/TOOLS.md)。

## 安装

需要 Python 3.11 或更高版本：

```sh
uv tool install luffysolution-omnischolar
# 或
pipx install luffysolution-omnischolar
# 或
python -m pip install luffysolution-omnischolar
```

如需从源码开发安装，请将包名替换为 `.`。

发行包名为 `luffysolution-omnischolar`，命令和 Python 包名都是 `omnischolar`。

检查安装结果：

```sh
omnischolar --version
omnischolar doctor --json
```

## 连接 Agent

### Codex App 与 Codex CLI 插件安装

先安装 [`uv`](https://docs.astral.sh/uv/getting-started/installation/)，再添加 OmniScholar Git Marketplace 并安装插件：

```sh
codex plugin marketplace add luffysolution-svg/omnischolar --ref main
codex plugin add omnischolar@omnischolar
```

在 ChatGPT 桌面应用中重启应用，打开 **Plugins**，选择 **OmniScholar** Marketplace，然后安装或启用 **OmniScholar**。在 Codex CLI 中可运行 `/plugins` 浏览同一 Marketplace。

插件会同时安装 8 个 Skills，并使用固定的 PyPI 版本启动本地 MCP：

```sh
uvx --from luffysolution-omnischolar==0.1.0 omnischolar mcp
```

采用插件安装方式时无需另外执行 `pip install`。第一次启动 MCP 需要联网，以便 `uvx` 下载并缓存包。各服务的凭据与可选配置仍保存在 OmniScholar 配置中，插件安装不会收集这些信息。

### Claude Code 插件安装

先安装 [`uv`](https://docs.astral.sh/uv/getting-started/installation/)。在 Claude Code 中添加 GitHub Marketplace 并安装插件：

```text
/plugin marketplace add luffysolution-svg/omnischolar
/plugin install omnischolar@omnischolar
```

如需在脚本或普通终端中执行，可使用非交互式命令：

```sh
claude plugin marketplace add luffysolution-svg/omnischolar
claude plugin install omnischolar@omnischolar --scope user
```

如果安装结果提示需要重新加载，请运行 `/reload-plugins`，然后新建会话。插件会自动启动同一个固定版本的 `uvx` MCP，并提供 `/omnischolar:scholar-search` 等带命名空间的 Skills，无需另行安装 Python 包。

### Agent 配置安装器

先查看将要修改的文件，再安装本地 MCP 配置和 Skills：

```sh
omnischolar install --dry-run claude
omnischolar install claude
```

可将 `claude` 换成 `codex`、`cursor`、`opencode`、`hermes`、`pi` 或 `workbuddy`。Codex、Claude Code、Cursor、OpenCode、Pi 和 WorkBuddy/CodeBuddy 支持用户级与项目级安装。Hermes 只提供用户级 MCP 配置；项目级命令会安装 Skills，并提示 MCP 需要手动设置。

```sh
omnischolar install cursor --scope project
omnischolar update cursor --scope project
omnischolar uninstall cursor --scope project
```

对 Pi，完整安装器会运行 `pi install npm:@luffysolution/omnischolar-pi`，并单独安装随包提供的 Skills。npm Extension 会启动 `omnischolar mcp`、发现工具并注册到 Pi。也可以直接安装 Extension：

```sh
pi install npm:@luffysolution/omnischolar-pi
```

WorkBuddy/CodeBuddy 的用户级配置位于 `~/.codebuddy/.mcp.json`，项目级配置位于 `.mcp.json`。其官方文档没有给出可移植的 Skills 目录，因此安装器会配置 MCP，并将 Skills 状态报告为 `manual_required`。

本地 MCP 命令为：

```sh
omnischolar mcp
```

通常无需手动运行，Agent 会根据 MCP 配置启动该进程。安装器写入受支持的配置后，会检查 `initialize`、`tools/list` 和 `omnischolar_status`。

各 Agent 的路径、更新和卸载方法见[安装说明](docs/INSTALLATION.md)。

## 使用示例

```text
查找 5 篇关于固态电池界面的近期综述，按 DOI 去重，并给出开放获取版本。

在我的 Zotero 中找到这个 DOI，汇总笔记和批注，不要修改 Zotero。

我确认上传后，用 MinerU 解析这份 PDF，并把阅读笔记保存到 Obsidian Vault。

查询 Materials Project 中稳定的 Li-Fe-P-O 材料，将选中的记录导出为 CSV 和 CIF。

为这个机理绘制带标签的示意图。图片只是草稿，不得写成实验数据。
```

## 配置

将 [`omnischolar.config.example.json`](omnischolar.config.example.json) 复制为 `omnischolar.config.json`。API key 建议放在环境变量中，配置文件只填写变量名 `apiKeyEnv`。

最小的本地配置可以只写 Zotero 和输出目录：

```json
{
  "schemaVersion": 1,
  "runtime": { "workspaceRoots": ["./research-inputs"] },
  "zotero": {
    "enabled": true,
    "baseUrl": "http://127.0.0.1:23119/api"
  },
  "output": { "rootDirectory": "./research-output" }
}
```

OpenAlex、PubMed、arXiv 和 Crossref 无需 API key。其他服务按需启用，字段和示例见[配置说明](docs/CONFIGURATION.md)。

## 文件、上传与费用

- Zotero 只连接本机 `23119` 端口，并且只发送 GET 请求。
- MinerU 只有在配置和本次工具调用都确认 `allowExternalUpload` 后，才会接收选中的 PDF。
- 图片服务会接收提示词，以及你允许上传的参考图；生成和编辑可能消耗账户额度。
- Ai4Scholar 的部分调用可能消耗账户额度。仅保存 API key 不代表同意付费调用。
- 付费请求发生网络错误后，如果无法确定服务端是否已经受理，OmniScholar 不会自动重试。
- AI 生成图只能作为示意图，不能当作测量数据、实验证据或科研结果。

启用上传或付费服务前，请阅读 [`PRIVACY.md`](PRIVACY.md) 和[配置说明](docs/CONFIGURATION.md)。

## 内置 Skills

| Skill | 用途 |
|---|---|
| `omnischolar` | 根据科研任务选择并组合工具 |
| `scholar-search` | 文献、专利、作者、引用网络、期刊和数据集 |
| `zotero-research` | 本地 Zotero 匹配、笔记、批注和附件 |
| `paper-reading` | MinerU 解析，以及正文、公式、表格和图片精读 |
| `academic-citation` | 证据核对、引用候选、格式化和参考文献 |
| `scientific-figure` | 科研图片生成、编辑、检查和标注 |
| `materials-project` | 材料筛选、性质、计算来源、相数据和导出 |
| `chemical-data` | 配置正式 API 说明后查询 CAS Common Chemistry |

## 文档

- [安装与 Agent 配置](docs/INSTALLATION.md)
- [配置与服务凭据](docs/CONFIGURATION.md)
- [文献、Zotero、MinerU、引用与输出](docs/RESEARCH.md)
- [材料与化学](docs/MATERIALS.md)
- [科研绘图服务](docs/IMAGE_PROVIDERS.md)
- [工具目录](docs/TOOLS.md)

## 支持与许可证

OmniScholar 使用 [MIT License](LICENSE) 开源。可在 [GitHub Issues](https://github.com/luffysolution-svg/omnischolar/issues) 提交问题，或发送邮件到 `LuffySolution@gmail.com`。报告问题前，请删除 API key、签名 URL、私人论文内容和个人 Zotero 数据。

第三方服务和数据仍遵循各自的条款与许可证，详见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
