# 科研绘图服务

[English](IMAGE_PROVIDERS.en.md)

OmniScholar 可连接 OpenAI、xAI、Gemini、Vertex AI、fal.ai、DashScope/Qwen、Atlas 和自定义 OpenAI 兼容服务。实际可用模型取决于账号、地区、服务地址和配置。

## 工具

| 工具 | 用途 |
|---|---|
| `omnischolar_image_models` | 发现并查看当前凭据可用模型及其功能 |
| `omnischolar_image_generate` | 文生图、图生图或多参考图生成 |
| `omnischolar_image_edit` | 编辑已有图片 |
| `omnischolar_image_service` | 调用服务商已经支持的状态、模型或任务操作 |
| `ai4scholar_figure` | 使用 Ai4Scholar 生成、编辑或矢量化图片 |

模型选择顺序是：用户显式指定的模型、当前服务商目录中已确认能力的模型、经过官方文档核对的内置模型、显式配置的模型合同。省略模型时，工具会发现并选择最新的可用模型；没有模型目录的服务商使用内置的已核对模型，同时仍允许在 `models` 中显式覆盖或补充模型和能力。

常用工具参数包括 `size`、`aspectRatio`、`resolution`、`background`、`outputFormat`、`quality`、`n`、`negativePrompt` 和 `seed`。调用前先读取模型描述中的 `supported_parameters`；工具会按服务商协议转换参数，不支持的参数组合会在提交请求前返回 `parameter_unsupported`，不会静默丢弃参数。

### 官方参数能力矩阵

| 服务商/API | 已核对的参数 | 明确不应默认传入 |
|---|---|---|
| OpenAI GPT Image | `size`/`resolution`、`background`、`outputFormat`、`quality`、`n` | 独立 `aspectRatio` |
| Google Gemini API Interactions | `aspectRatio`、`resolution`（`1K`/`2K`）、`outputFormat` | `size`、`background`、`quality`、`n`、`seed` |
| Vertex Gemini image | `aspectRatio`、`resolution`（`1K`/`2K`/`4K`）、`outputFormat`、`n` | 透明背景、任意像素尺寸 |
| Fal Nano Banana 2 | `aspectRatio`、`resolution`、`outputFormat`、`n`、`seed` | `background`、`quality` |
| Fal GPT Image 变体 | `size`/`resolution`、`background`、`outputFormat`、`quality`、`n` | Nano Banana 专属参数 |
| DashScope/Qwen 原生图像 | `size`/`resolution`、`n`、`negativePrompt`、`seed` | `background`、`quality`、透明背景 |
| Atlas | 按模型合同；GPT Image 常见为 `size`、`quality`、`outputFormat` | 不要使用服务商级统一假设 |

## 配置示例

```json
{
  "schemaVersion": 1,
  "defaults": {
    "defaultImageProvider": "fal"
  },
  "media": {
    "providers": {
      "fal": {
        "enabled": true,
        "apiKeyEnv": "OMNISCHOLAR_FAL_API_KEY",
        "baseUrl": "https://queue.fal.run",
        "models": {},
        "options": {}
      },
      "dashscope": {
        "enabled": true,
        "apiKeyEnv": "OMNISCHOLAR_DASHSCOPE_API_KEY",
        "baseUrl": "https://your-workspace.cn-beijing.maas.aliyuncs.com/api/v1",
        "models": {},
        "options": {
          "workspace": "your-workspace",
          "region": "cn-beijing",
          "protocol": "native"
        }
      },
      "qwen-cloud": {
        "enabled": true,
        "apiKeyEnv": "OMNISCHOLAR_QWEN_API_KEY",
        "baseUrl": "https://dashscope.aliyuncs.com/api/v1",
        "models": {},
        "options": {
          "protocol": "native"
        }
      }
    }
  }
}
```

千问 AI 平台图片模型使用公共 DashScope 原生接口 `https://dashscope.aliyuncs.com/api/v1`，不需要 workspace 或 region。只有百炼的地域 workspace 实例才需要填写 `workspace`、`region`，并使用对应的 workspace Base URL。`protocol` 默认是 `native`，只有明确配置为 `openai-compatible` 时才使用兼容端点。内置模型包括 `qwen-image-3.0-pro`、`qwen-image-3.0`、`wan2.7-image-pro`、`wan2.7-image` 和 `z-image-turbo`；其中当前 Qwen Image 3.0 推荐模型为 `qwen-image-3.0-pro`，具体生成权限仍以账号和地域为准。

Vertex AI 可使用 service-account JSON：

```json
{
  "vertex": {
    "enabled": true,
    "credentialsFile": "F:/path/to/service-account.json",
    "project": null,
    "location": "global",
    "models": {
      "imagen-3.0-capability-001": {
        "capabilities": ["text-to-image", "image-to-image", "edit"]
      }
    }
  }
}
```

服务账号文件只用于本地换取 OAuth token，不会写入输出结果。若省略 `project`，工具会从 JSON 的 `project_id` 自动读取；默认 `location` 为 `global`。模型是否可用仍取决于项目授权、区域和模型发布状态。

Atlas、fal、Vertex、DashScope/Qwen 和自定义服务的模型目录能力不同。Atlas、fal、Vertex、DashScope/Qwen 已提供少量基于官方文档核对的内置模型；自定义服务仍需要准确的 `baseUrl`、模型 ID、功能列表，以及生成或编辑接口。不要只凭模型名填写功能，也不要把内置模型视为账号已开通的保证。

## 生成与编辑

提交任务前应明确图片要表达的科学内容、标签、单位、比例和文件格式。配置好图片服务 API key 后即可直接生成或上传参考图。

只能上传有权交给第三方处理的图片。图片保存后，返回结果中的签名 URL 和 base64 原文会被移除。下载文件会检查 HTTPS 地址、文件大小、MIME 类型和图片文件头；多文件任务缺少任一文件时，不发布不完整结果。

## 当前服务说明

- fal 已验证队列提交、轮询、data URI 结果、文生图和双参考图编辑。本机若无法解析 fal CDN，data URI 结果仍可保存。
- Fal 默认使用官方 `sync_mode=true`，直接保存 data URI，不需要下载输出 CDN；可通过 `options.sync_mode=false` 选择传统远程 URL 流程。
- DashScope/Qwen 支持千问 AI 平台的通用原生地址 `https://dashscope.aliyuncs.com/api/v1`，也支持百炼按地域的 workspace 地址，例如 `https://<workspace>.cn-beijing.maas.aliyuncs.com/api/v1`。当填写 `workspace` 和 `region` 时，工具可以自动拼接地域地址。
- Gemini 配置中的 `apiKeyEnv` 必须指向已存在的环境变量。
- Atlas Cloud 使用 `https://api.atlascloud.ai/api/v1`、`model/generateImage` 提交和 `model/prediction/{id}` 轮询；默认内置 Nano Banana 2、GPT Image 2、GPT Image 2.5 Flare/Sunburst 的官方模型 ID。Atlas 的图片任务是异步的，结果中的 `outputs` 会保存到本地。
- 自定义服务必须给出可用的服务地址与模型说明。

生成后仍需人工检查文字、结构、机制、比例和定量描述。**AI 图片是示意草稿，不是实验数据、真实测量或科研结论。**
