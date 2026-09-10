# 配置

[English](CONFIGURATION.en.md)

OmniScholar 使用 `schemaVersion: 1` 的 JSON 配置。可直接复制根目录的 [`omnischolar.config.example.json`](../omnischolar.config.example.json)，再删除不需要的服务。

## 配置文件位置

程序使用找到的第一个配置文件，不合并多份配置：

1. `--config PATH` 指定的文件
2. `OMNISCHOLAR_CONFIG` 指向的文件
3. 当前项目的 `omnischolar.config.json`
4. 用户配置目录中的 `omnischolar/omnischolar.config.json`
5. 内置默认值

相对路径以配置文件所在目录为基准。拼错字段名或填写不合法的值时，程序会直接报错。

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

## API key

建议把 key 存入环境变量，配置中只写变量名：

```json
{
  "schemaVersion": 1,
  "ai4scholar": {
    "enabled": true,
    "apiKeyEnv": "OMNISCHOLAR_AI4SCHOLAR_API_KEY",
    "allowPaid": false
  },
  "data": {
    "materialsProject": {
      "enabled": true,
      "apiKeyEnv": "OMNISCHOLAR_MATERIALS_PROJECT_API_KEY"
    }
  }
}
```

读取顺序为 `apiKey`、`apiKeyEnv` 指向的环境变量、该服务的默认环境变量。不要把明文 key 写入 Agent 的 MCP 配置、Skills、命令行或版本库。

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

保存 key 不会自动允许付费或上传。

- Ai4Scholar 和图片生成需在配置中启用 `allowPaid`，调用时还要再次确认 `allowPaid`。
- MinerU 与参考图上传需在配置中启用 `allowExternalUpload`，调用时还要再次确认同名参数。
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
    "model": "pipeline",
    "allowExternalUpload": false
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

