# 科研绘图服务

[English](IMAGE_PROVIDERS.en.md)

OmniScholar 可连接 OpenAI、xAI、Gemini、Vertex AI、fal.ai、DashScope/Qwen、Atlas 和自定义 OpenAI 兼容服务。实际可用模型取决于账号、地区、服务地址和配置。

## 工具

| 工具 | 用途 |
|---|---|
| `omnischolar_image_models` | 查看已配置模型及其可用功能 |
| `omnischolar_image_generate` | 文生图、图生图或多参考图生成 |
| `omnischolar_image_edit` | 编辑已有图片 |
| `omnischolar_image_service` | 调用服务商已经支持的状态、模型或任务操作 |
| `ai4scholar_figure` | 使用 Ai4Scholar 生成、编辑或矢量化图片 |

每个模型都必须明确声明支持的功能。模型名出现在服务商目录中，并不自动代表它可以生图或编辑；`omnischolar_image_models` 中对应功能需要显示 `usable: true`。

## 配置示例

```json
{
  "schemaVersion": 1,
  "defaults": {
    "defaultImageProvider": "fal"
  },
  "media": {
    "allowPaid": false,
    "allowExternalUpload": false,
    "providers": {
      "fal": {
        "enabled": true,
        "apiKeyEnv": "OMNISCHOLAR_FAL_API_KEY",
        "baseUrl": "https://fal.run",
        "models": {},
        "options": {}
      }
    }
  }
}
```

自定义服务需要填写准确的 `baseUrl`、模型 ID、功能列表，以及生成或编辑接口。不要只凭模型名填写功能。

## 生成与编辑

提交任务前应明确图片要表达的科学内容、标签、单位、比例和文件格式。生成需要本次 `allowPaid` 授权；上传参考图还需要本次 `allowExternalUpload` 授权。

只能上传有权交给第三方处理的图片。图片保存后，返回结果中的签名 URL 和 base64 原文会被移除。下载文件会检查 HTTPS 地址、文件大小、MIME 类型和图片文件头；多文件任务缺少任一文件时，不发布不完整结果。

## 当前服务说明

- fal 已验证队列提交、轮询、data URI 结果、文生图和双参考图编辑。本机若无法解析 fal CDN，data URI 结果仍可保存。
- DashScope/Qwen 当前需要绑定 workspace 的服务地址，或服务商明确提供的 `baseUrl`。旧通用地址会返回 `dashscope_workspace_required`。
- Gemini 配置中的 `apiKeyEnv` 必须指向已存在的环境变量。
- Atlas 和自定义服务必须给出可用的服务地址与模型说明。

生成后仍需人工检查文字、结构、机制、比例和定量描述。**AI 图片是示意草稿，不是实验数据、真实测量或科研结论。**
