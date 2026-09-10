# 文献、Zotero 与 PDF

[English](RESEARCH.en.md)

## 文献检索

| 工具 | 用途 |
|---|---|
| `research_sources` | 查看已启用的数据源和可用功能 |
| `literature_search` | 检索论文，可限制年份、类型和开放获取状态 |
| `literature_get` | 按 DOI、PMID/PMCID、arXiv ID 或数据源 ID 获取详情 |
| `literature_graph` | 查询参考文献、施引文献或推荐论文 |
| `journal_metrics` | 查询已支持的期刊指标 |
| `literature_fulltext` | 查找合法全文地址，或将允许访问的文件保存到输出目录 |

各数据源侧重点不同：

- Semantic Scholar 和 OpenAlex 适合跨学科检索与引用关系。
- PubMed/PMC 适合生物医学文献，PMC 还能提供带许可信息的开放全文。
- arXiv 保留预印本标识符和版本信息。
- Crossref 适合核对 DOI 注册元数据。
- Unpaywall 用于查找开放获取版本，不绕过订阅或访问控制。
- easyScholar 提供当前接口支持的期刊指标。
- Ai4Scholar 还可查询 Google Scholar、Google Patents、作者、数据集和期刊信息，部分调用会消耗额度。

检索时先用较小的 `limit`。优先按 DOI 去重；没有 DOI 时，再比较标题、年份和第一作者。标题相似只能用于筛选，不能代替正文证据。

遇到 HTTP 429 时，OmniScholar 会返回限流信息。等待服务商给出的时间后再试，或改用支持同一查询的数据源。不要连续提交相同请求。

## Zotero

OmniScholar 只连接本机 Zotero API：

```text
http://127.0.0.1:23119/api
```

需要在 Zotero 中开启“允许其他应用程序与 Zotero 通信”，并保持 Zotero Desktop 运行。

| 工具 | 可读取内容 |
|---|---|
| `zotero_collections` | 收藏夹及其条目 |
| `zotero_search` | 文献条目、笔记、批注和附件 |
| `zotero_item` | 单个条目或聚合后的论文视图 |

聚合视图可包含书目信息、笔记、批注、附件信息、索引文本和本地 PDF 路径。OmniScholar 不会创建、修改、移动、加标签或删除 Zotero 数据。

Zotero 笔记和批注属于个人阅读记录，不应当作论文原文证据。需要引用论文结论时，仍要核对原文。

## MinerU 解析

`omnischolar_parse` 检查 PDF 文件、计算 SHA-256，并使用 MinerU 返回正文、公式、表格和图片。解析结果会缓存；同一文件和解析设置再次调用时可直接命中缓存。

上传必须同时得到两次确认：

1. 配置中的 `mineru.allowExternalUpload` 为 `true`；
2. 本次 `omnischolar_parse` 调用中的 `allowExternalUpload` 为 `true`。

OmniScholar 不会自动把 Zotero 附件上传到 MinerU。应先确认具体条目和文件，再单独批准上传。`force` 会重新解析并产生一次新上传，因此也需要新的授权。

下载的 MinerU 压缩包会在解压前检查路径、符号链接、文件数量和展开大小。检查失败时不写入输出目录。

## 引用

引用工作分为两步：先确认来源是否支持论点，再格式化书目信息。

1. 用 `literature_search` 和 `literature_get` 查找来源。
2. 核对 DOI、PMID、arXiv ID、标题、作者和年份。
3. 阅读与论点相关的正文段落。
4. 使用 `ai4scholar_citation_candidates` 补充候选时，先确认付费调用。
5. 只对已核对的记录使用 `ai4scholar_cite`。

格式正确的参考文献不代表论点已经得到支持。Ai4Scholar 的 Google Scholar 引用格式化目前可能缺少接口要求的结果 ID；遇到 `blocked` 时，不要自行拼接 ID。

## 保存到 Markdown 或 Obsidian

`omnischolar_sync` 会先给出计划，再写入 `output.rootDirectory`。该目录可以是普通文件夹，也可以位于 Obsidian Vault 中。

同步会区分新建、无需更新、元数据变化、解析变化、渲染变化、文件缺失、冲突、排除和中断恢复。仅修复元数据、渲染或中断事务时不会上传 PDF。

若已生成的 Markdown 被手工修改，默认策略会保留现有文件，并把新版本写入 `.conflicts/`。检查两份内容后再决定如何合并。

首次写入真实 Vault 前，可先把 `output.rootDirectory` 指向临时目录，确认目录名、Markdown 和图片路径符合预期。
