# 配置

[English](CONFIGURATION.en.md)

OmniScholar 使用 `schemaVersion: 1` 的 JSON 配置。可直接复制根目录的 [`omnischolar.config.example.json`](../omnischolar.config.example.json)，再删除不需要的服务。

## 配置文件位置

程序使用找到的第一个配置文件，不合并多份配置：

1. `--config PATH` 指定的文件
2. `OMNISCHOLAR_CONFIG` 指向的文件
3. 当前项目的 `omnischolar.config.json`
4. 用户配置目录中的 `omnischolar.config.json`
5. 内置默认值

相对路径以配置文件所在目录为基准。拼错字段名或填写不合法的值时，程序会直接报错。

示例配置中的服务默认启用。填写对应 API key 后即可直接使用。

如果前四项都不存在，第一次启动 MCP 或执行安装命令时会自动创建用户级完整配置模板。模板包含所有服务区块、`apiKey`、`apiKeyEnv` 以及 Vertex 的 `project`、`location` 等字段；Windows 通常位于 `%LOCALAPPDATA%\omnischolar\omnischolar.config.json`，Linux 通常位于 `~/.config/omnischolar/omnischolar.config.json`，macOS 通常位于 `~/Library/Application Support/omnischolar/omnischolar.config.json`。也可以运行 `omnischolar config init` 主动创建；程序不会覆盖已有配置。旧版本生成的嵌套目录文件不会自动迁移或读取，请按需手动复制设置。

## 最小配置

```json
{
  "schemaVersion": 1,
  "runtime": {
    "workspaceRoots": ["./research-inputs"],
    "requestTimeoutSeconds": 30
  },
  "zotero": {
    "enabled": true,
    "baseUrl": "http://127.0.0.1:23119/api"
  },
  "output": {
    "rootDirectory": "./research-output"
  }
}
```

`workspaceRoots` 限定可读取的本地文件，`output.rootDirectory` 限定写入位置。若要直接写入 Obsidian，可把输出目录设为 Vault 中的一个文件夹。

核心服务支持 Windows、Linux 和 macOS。Zotero 功能需要本机运行 Zotero Desktop；XRD 计算需要可选的 `pymatgen` 后端。

`omnischolar_status` 不显示配置文件绝对路径；需要查看路径时使用 `omnischolar config path`。

新文献的子文件夹和文件名可以继续细分：

```json
{
  "output": {
    "rootDirectory": "F:/个人知识库",
    "literatureDirectory": "文献/已解析",
    "folderNameTemplate": "{author}{separator}{year}",
    "filenameTemplate": "{year}{separator}{author}{separator}{title}",
    "filenameSeparator": "+",
    "assetFilenameTemplate": "figure{separator}{index}{separator}{original}{extension}"
  }
}
```

文献和文件夹模板支持 `{author}`、`{year}`、`{title}`、`{separator}`；`folderNameTemplate` 控制每篇文献目录名。连接符目前支持 `-`、`+` 和 `_`，并由文献、文件夹、附件模板共用。附件图片模板支持 `{index}`、`{original}`、`{extension}`、`{separator}`。这些设置只影响新建文献，已有同步记录沿用 manifest 中的路径。这里的附件图片是解析生成的图片，不是 Zotero 原始 PDF 附件。

## API key

API key 可以直接写入对应服务的 `apiKey`。例如：

```json
{
  "schemaVersion": 1,
  "ai4scholar": {
    "enabled": true,
    "apiKey": "在这里填写 Ai4Scholar API key"
  },
  "data": {
    "materialsProject": {
      "enabled": true,
      "apiKey": "在这里填写 Materials Project API key"
    }
  }
}
```

也可以只填写变量名，让程序从环境变量读取：

```json
{
  "mineru": {
    "enabled": true,
    "apiKeyEnv": "OMNISCHOLAR_MINERU_API_KEY"
  }
}
```

读取顺序为 `apiKey`、`apiKeyEnv` 指向的环境变量、该服务的默认环境变量。直接写入配置文件最简单，但该文件包含敏感信息，请限制文件权限，不要提交到版本库或复制到 Agent 的 MCP 配置中。

| 服务 | 是否需要 key 或其他信息 |
|---|---|
| OpenAlex、PubMed、arXiv、Crossref | 基本检索无需 key；PubMed key 可提高 NCBI 请求额度 |
| Semantic Scholar | key 可选；匿名共享流量更容易遇到 429 |
| Unpaywall | 需要联系邮箱 |
| easyScholar | 需要 API key |
| Zotero | 不需要 key；需开启本地 API |
| MinerU | 需要 API key，并确认 PDF 上传 |
| Ai4Scholar | 需要 API key，部分调用消耗额度 |
| Materials Project | 需要 API key |
| 图片服务 | 按服务商要求配置 key、模型和服务地址 |
| CAS Common Chemistry | 当前还需要服务商提供的正式接口说明文件 |

## 付费与上传

填写对应 API key 后即可使用 Ai4Scholar、图片生成、MinerU 和参考图上传。CAS 需要正式接口契约文件，DashScope/Qwen 需要 workspace 地址。
- 同步恢复只处理本地文件，不会沿用以前的上传许可。
- 付费请求超时后，如果服务端结果不明确，程序不会自动重试。

## 文献检索

```json
{
  "schemaVersion": 1,
  "research": {
    "fallback": true,
    "maxPages": 5,
    "providers": {
      "openalex": { "enabled": true, "email": "researcher@example.org" },
      "pubmed": { "enabled": true, "email": "researcher@example.org" },
      "arxiv": { "enabled": true },
      "crossref": { "enabled": true, "email": "researcher@example.org" },
      "unpaywall": { "enabled": true, "email": "researcher@example.org" }
    }
  }
}
```

`fallback` 只会改用支持同一项查询的服务。HTTP 429 会作为限流结果返回，不会触发连续重试。

## MinerU

```json
{
  "schemaVersion": 1,
  "mineru": {
    "enabled": true,
    "apiKeyEnv": "OMNISCHOLAR_MINERU_API_KEY",
    "model": "pipeline"
  }
}
```

默认不启用 MinerU v1 备用接口。当前文档对页数限制的描述不一致，因此程序不会自行切换接口。

## 检查配置

```sh
omnischolar config path
omnischolar config schema
omnischolar status
omnischolar doctor --json
```

