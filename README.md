# OmniScholar

<!-- mcp-name: io.github.luffysolution-svg/omnischolar -->

[![PyPI](https://img.shields.io/pypi/v/luffysolution-omnischolar?logo=pypi&label=PyPI)](https://pypi.org/project/luffysolution-omnischolar/)
[![npm](https://img.shields.io/npm/v/%40luffysolution%2Fomnischolar-pi?logo=npm&label=npm)](https://www.npmjs.com/package/@luffysolution/omnischolar-pi)
[![npx Skills](https://img.shields.io/badge/npx%20Skills-supported-CB3837?logo=npm&logoColor=white)](https://www.npmjs.com/package/skills)
[![Release](https://img.shields.io/github/v/release/luffysolution-svg/omnischolar?logo=github)](https://github.com/luffysolution-svg/omnischolar/releases)

简体中文 | [English](README.en.md)

OmniScholar 通过本地 Python MCP 服务，为 Codex、Claude Code、Cursor、OpenCode、Hermes 和 Pi 提供文献检索、Zotero 读取、PDF 解析、引用处理、材料数据和科研绘图工具。

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

<details>
<summary>安装与部署</summary>

需要 Python 3.11 或更高版本。普通 Python 命令任选一种方式安装：

```sh
uv tool install luffysolution-omnischolar
# 或
pipx install luffysolution-omnischolar
# 或
python -m pip install luffysolution-omnischolar
```

检查、更新和卸载：

```sh
omnischolar --version
omnischolar doctor --json
uv tool upgrade luffysolution-omnischolar
uv tool uninstall luffysolution-omnischolar
```

如果希望用一条命令强制刷新并重装最新版：

```sh
uv tool install --reinstall luffysolution-omnischolar
```

### Codex 插件

```sh
codex plugin marketplace add luffysolution-svg/omnischolar --ref main
codex plugin add omnischolar@omnischolar

# 更新已安装的 Codex 插件
codex plugin marketplace upgrade omnischolar
codex plugin remove omnischolar@omnischolar
codex plugin add omnischolar@omnischolar
```

ChatGPT 桌面应用中重启应用后打开 **Plugins**，选择 **OmniScholar** 并安装或启用；Codex CLI 可运行 `/plugins` 浏览插件。插件已经包含 Skills，并通过下面的命令启动 PyPI 最新 MCP：

```sh
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```

### Claude Code 插件

在 Claude Code 会话中运行：

```text
/plugin marketplace add luffysolution-svg/omnischolar
/plugin install omnischolar@omnischolar
```

普通终端也可以运行：

```sh
claude plugin marketplace add luffysolution-svg/omnischolar
claude plugin install omnischolar@omnischolar --scope user
claude plugin update omnischolar@omnischolar --scope user
```

### Pi Extension

```sh
pi install npm:@luffysolution/omnischolar-pi
pi update npm:@luffysolution/omnischolar-pi
pi remove npm:@luffysolution/omnischolar-pi
```

### 通用安装器与独立 Skills

```sh
omnischolar install --dry-run claude
omnischolar install claude
omnischolar update claude
omnischolar uninstall claude
```

也可以使用官方 Skills CLI 单独安装 Skills；插件已经包含这些 Skills，通常不需要重复安装：

```sh
npx skills add luffysolution-svg/omnischolar --skill '*' --agent codex --global --yes
npx skills update --global --yes
npx skills remove --skill '*' --agent codex --global --yes
```

完整的各 Agent 路径、项目级安装和故障排查见[安装说明](docs/INSTALLATION.md)。

</details>

## Agent 配置提示词

可以将下面的提示词作为 Agent 的项目级指令或系统提示词基础：

```text
你是我的科研助理，使用 OmniScholar 完成文献检索、Zotero 阅读、PDF 解析、引用核对和科研资料整理。检索时优先使用可靠的学术来源，核对 DOI 与书目信息，并明确区分原文证据、推断和不确定内容。Zotero 只允许读取，禁止修改。上传 PDF、参考图或发起可能收费的请求前必须先征得我的确认；MinerU 只有在我确认后才能上传文件。将确认后的文献笔记和生成文件保存到配置的输出目录，保留已有手工修改，并报告最终文件路径。生成的科研图片只能作为示意图，不能当作实验数据或科研证据。
```

## 配置与 MCP 示例

首次启动 MCP 或运行安装器时，如果没有可发现的配置，OmniScholar 会创建用户级 `omnischolar.config.json` 模板。模板中的服务默认处于启用状态；填写 API key 后即可使用对应服务，没有凭据的服务不会自动发起请求。API key 可以直接填写到 `apiKey`，也可以用 `apiKeyEnv` 指定环境变量。

填写对应 API key 并启用服务后，即可直接使用 Ai4Scholar、图片生成、MinerU 和参考图上传。

根目录的 [`mcp.json`](mcp.json) 是可直接复制到支持 MCP 的 Agent 中的 stdio 示例，内容如下：

```json
{
  "mcpServers": {
    "omnischolar": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--refresh-package", "luffysolution-omnischolar", "--from", "luffysolution-omnischolar@latest", "omnischolar", "mcp"]
    }
  }
}
```

`mcp.json` 只负责启动 MCP，不保存 API key；服务凭据和 Obsidian 输出位置填写在 [`omnischolar.config.example.json`](omnischolar.config.example.json) 对应字段中，可执行 `omnischolar config init` 创建实际配置。插件内部使用的配置文件是 [`.mcp.json`](.mcp.json)。文件夹、Markdown 文件和图片附件命名可通过 `output` 区块自定义，详见[文献与输出配置](docs/RESEARCH.md)。

## 使用示例

```text
查找 5 篇关于固态电池界面的近期综述，按 DOI 去重，并给出开放获取版本。

在我的 Zotero 中找到这个 DOI，汇总笔记和批注，不要修改 Zotero。

我确认上传后，用 MinerU 解析这份 PDF，并把阅读笔记保存到 Obsidian Vault。

查询 Materials Project 中稳定的 Li-Fe-P-O 材料，将选中的记录导出为 CSV 和 CIF。

为这个机理绘制带标签的示意图。图片只是草稿，不得写成实验数据。
```

## 文档

- [安装与 Agent 配置](docs/INSTALLATION.md)
- [配置与服务凭据](docs/CONFIGURATION.md)
- [文献、Zotero、MinerU、引用与输出](docs/RESEARCH.md)
- [材料与化学](docs/MATERIALS.md)
- [科研绘图服务](docs/IMAGE_PROVIDERS.md)
- [工具目录](docs/TOOLS.md)

## 支持与许可证

OmniScholar 使用 [MIT License](LICENSE) 开源。可以在 [GitHub Issues](https://github.com/luffysolution-svg/omnischolar/issues) 提交问题，或发送邮件到 `LuffySolution@gmail.com`。报告问题前，请删除 API key、签名 URL、私人论文内容和个人 Zotero 数据。

第三方服务和数据遵循各自的条款与许可证，详见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
