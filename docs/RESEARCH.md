# 文献、Zotero 与 PDF

[English](RESEARCH.en.md)

## 文献检索

| 工具 | 用途 |
|---|---|
| `research_sources` | 查看已启用的数据源和可用功能 |
| `literature_search` | 检索论文，可限制年份、类型和开放获取状态 |
| `literature_get` | 按 DOI、PMID/PMCID、arXiv ID 或数据源 ID 获取详情 |
| `literature_author` | 查询 Semantic Scholar 作者、作者详情或作者论文列表 |
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

遇到 HTTP 429 时，OmniScholar 会读取 `Retry-After`（若服务商提供），并对 Semantic Scholar 使用有界退避和可选的 `rateLimitPerSecond`。仍应避免连续提交相同请求。

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

`zotero_item` 默认返回元数据；需要笔记、批注或 PDF 选择时再显式使用 `mode=aggregate`。已解析文献使用 `omnischolar_read` 按全文游标、图表、公式、段落、对比或综述模式分段读取，完整 Markdown 仍保存在输出目录，不会默认一次返回给 Agent。

### 聚焦检索与阅读上下文

已解析的本地文献可以用 `omnischolar_focus` 做有界的 BM25 + TF-IDF 向量混合证据检索。它返回匹配段落、章节、字符范围和 `paper.md#Lx-Ly` 行定位，不返回整篇 Markdown；可用 `keys`、`section`、`topK` 和 `maxPerDocument` 限定范围。当前本地后端会明确返回 `strategy=hybrid-bm25-tfidf`、`vectorBackend=tfidf-local` 和 `semantic=false`，因此不会把词项向量相似度误称为真正的语义 embedding 检索。

需要单篇精确定位时使用 `omnischolar_locate`，按短语或全部词项匹配段落，并保留 Zotero key、标题、章节和定位锚点。图表读取使用 `omnischolar_read` 的 `figures` 模式，返回图片路径、表格 Markdown、标题以及受限的图表上下文；Agent 仍需区分图像观察、图注、作者结论和自己的解释。

多轮阅读可以先用 `omnischolar_context` 的 `open` 创建上下文，再把 `contextId` 传给 `omnischolar_focus`、`omnischolar_locate` 或 `omnischolar_read`。缓存只保存选中的证据片段，`get` 仍然分页并受字符上限约束，不会自动把整篇论文再次注入 Agent。`compare` 和 `review` 模式也可以把每篇文献的有界证据加入同一个上下文。

Zotero 笔记和批注属于个人阅读记录，不应当作论文原文证据。需要引用论文结论时，仍要核对原文。

## MinerU 解析

`omnischolar_parse` 检查 PDF 文件、计算 SHA-256，并使用 MinerU 返回正文、公式、表格和图片。解析结果会缓存；同一文件和解析设置再次调用时可直接命中缓存。工具结果只返回解析摘要、文件路径和发布信息；正文通过 `omnischolar_read` 按需读取。

配置好 MinerU API key 并启用服务后即可解析；OmniScholar 不会在没有凭据时自动上传。

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

输出位置和新文件命名可以在全局配置中自定义：

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

支持的文献文件名变量为 `{author}`、`{year}`、`{title}` 和 `{separator}`；`folderNameTemplate` 单独控制每篇文献目录名。`filenameSeparator` 当前支持 `-`、`+` 和 `_`，会同时提供给文献、文件夹和附件模板。附件图片支持 `assetFilenameTemplate`，变量为 `{index}`、`{original}`、`{extension}` 和 `{separator}`。新文献会写入 `rootDirectory/literatureDirectory`，图片放在每篇文献目录下的 `assets/`。已有 manifest 记录会沿用原路径，避免改配置后破坏增量同步。这里的附件图片是解析结果中的图片，不是 Zotero 原始 PDF 附件。

若 `output.source.copyPdf` 为 true，选中的 Zotero PDF 会复制到每篇文献目录的 `source/`，并生成 `zotero-reading-record.md`。该文件将 Zotero 笔记和 PDF 批注分成两个区块，批注保留类型、颜色、页码、标签、评论和 PDF 相对链接；它们属于个人阅读记录，不应直接作为论文原文证据。

结构化解读通过 `omnischolar_analysis` 写入：

- `full-read`：单篇 SCI 文献精读；
- `targeted-reading`：单篇针对性解读，聚焦图表、公式、机制、方法、现有笔记和关联文献；
- `compare`：用户选定多篇文献的紧凑对比矩阵；
- `review`：多篇文献的主题性、叙述性、系统性或范围综述。

默认输出为 `Analysis/Single/<paper>/` 和 `Analysis/Multi/`，路径和文件名由 `output.source`、`output.analysis` 配置。工具会保存来源 fingerprint 和相对链接，默认不会覆盖手工修改的分析文件。

`omnischolar_sync` 会先给出计划，再写入 `output.rootDirectory`。该目录可以是普通文件夹，也可以位于 Obsidian Vault 中。

同步会区分新建、无需更新、元数据变化、解析变化、渲染变化、文件缺失、冲突、排除和中断恢复。仅修复元数据、渲染或中断事务时不会上传 PDF。

若已生成的 Markdown 被手工修改，默认策略会保留现有文件，并把新版本写入 `.conflicts/`。检查两份内容后再决定如何合并。

首次写入真实 Vault 前，可先把 `output.rootDirectory` 指向临时目录，确认目录名、Markdown 和图片路径符合预期。
