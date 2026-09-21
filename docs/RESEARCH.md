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

`zotero_item` 默认返回元数据；需要笔记、批注或 PDF 选择时再显式使用 `mode=aggregate`。`paper-reading` 只负责选择 PDF 并准备 MinerU 原文与资产；完成解析后的完整精读、聚焦问题、证据定位以及图表或公式解读统一由 `literature-reading` 使用宿主的本地文件能力完成。

### 本地文献解读

如果用户没有指定局部问题，`literature-reading` 默认对整篇论文进行专业解读，并覆盖实际存在的主要章节，而不是只读摘要与结论。解读应直接读取 MinerU Markdown，逐步定位原文证据，并区分论文证据、作者解释、Agent 的解释和不确定性。只有用户要求保存或内容长到不适合在对话中呈现时，才生成 Markdown 文件。

图表解读必须同时核对 MinerU 图片资产、图注和作者在正文中的相关表述。视觉观察、作者结论和 Agent 推断要分开表达；不能仅凭图注猜测图片内容。输出文件中的图片使用 MinerU 实际资产路径，并以可预览、可点击的相对链接嵌入。

Zotero 笔记和批注属于个人阅读记录，不应当作论文原文证据。需要引用论文结论时，仍要核对原文。

## MinerU 解析

`omnischolar_parse` 检查 PDF 文件、计算 SHA-256，并使用 MinerU 返回正文、公式、表格和图片。解析结果会缓存；同一文件和解析设置再次调用时可直接命中缓存。工具结果返回解析摘要和发布路径；Skill 从返回的 `publication.markdownPath` 找到原文，再读取同级的图片资产。

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

支持的文献文件名变量为 `{author}`、`{year}`、`{title}` 和 `{separator}`；`folderNameTemplate` 单独控制每篇文献目录名。`filenameSeparator` 支持 `-`、`+` 和 `_`，会同时提供给文献、文件夹和附件模板。`assetFilenameTemplate` 控制 Zotero key 后面的图片名称部分，变量为 `{index}`、`{original}`、`{extension}` 和 `{separator}`。每张解析图片都以 `<zoteroKey><separator>` 开头；默认名称类似 `ABCD1234-image-1.png`。新文献写入 `rootDirectory/literatureDirectory`，图片位于每篇文献目录下的 `assets/`。若不同 Zotero 文献生成相同目录名，后创建的目录会附加 Zotero key，避免覆盖已有文献。已有 manifest 记录会沿用原路径，避免改配置后破坏增量同步。这里的附件图片是解析结果中的图片，不是 Zotero 原始 PDF 附件。

MinerU 原文和 `source/zotero-reading-record.md` 都包含可供 Obsidian 读取的 YAML frontmatter：`recordType`、`title`、`itemType`、`creators`、`zoteroKey`、`DOI`、`URL`、`publicationTitle`、`tags`、`abstract`、`collections` 和 `zoteroLink`。阅读记录还包含 `sourceKinds`。`creators` 使用姓名列表，`zoteroLink` 可直接跳转到本地 Zotero 条目。Zotero 标签中的空格会转换为连字符，不适用于 Obsidian 标签的符号也会安全转换；纯数字标签会增加 `tag-` 前缀。

解析并发布论文时会在每篇文献目录的 `source/` 中生成 `zotero-reading-record.md`。若 `output.source.copyPdf` 为 true，选中的 Zotero PDF 也会复制到该目录。阅读记录将 Zotero 笔记和 PDF 批注分成两个区块，批注保留类型、颜色、页码、标签、评论和 PDF 相对链接；它们属于个人阅读记录，不应直接作为论文原文证据。

需要保存时，`literature-reading` 默认把解读文件写入 MinerU Markdown 所在的文献目录，用户也可以指定其他位置。Skill 保持原文和图片资产不变；同名文件已经存在时不得静默覆盖。图表使用类似 `[![Figure](assets/ABCD1234-image-1.png)](assets/ABCD1234-image-1.png)` 的相对链接，既可预览也可打开原始 MinerU 图片资产。

`omnischolar_sync` 会先给出计划，再写入 `output.rootDirectory`。该目录可以是普通文件夹，也可以位于 Obsidian Vault 中。

如果一个 Zotero 条目包含多个 PDF，先用聚合读取结果列出附件键和文件名，并请用户确认。只有带明确 `attachmentKey` 的解析或同步调用才会继续，避免静默选择错误附件。

同步会区分新建、无需更新、元数据变化、解析变化、渲染变化、文件缺失、冲突、排除和中断恢复。仅修复元数据、渲染或中断事务时不会上传 PDF。

若已生成的 Markdown 被手工修改，默认策略会保留现有文件，并把新版本写入 `.conflicts/`。检查两份内容后再决定如何合并。

首次写入真实 Vault 前，可先把 `output.rootDirectory` 指向临时目录，确认目录名、Markdown 和图片路径符合预期。
