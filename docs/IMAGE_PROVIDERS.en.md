# Scientific image services

[简体中文](IMAGE_PROVIDERS.md)

OmniScholar can connect to OpenAI, xAI, Gemini, Vertex AI, fal.ai, DashScope/Qwen, Atlas, and custom OpenAI-compatible services. Available models depend on the account, region, endpoint, and configuration.

## Tools

| Tool | Use |
|---|---|
| `omnischolar_image_models` | Discover and show models available with the current credentials |
| `omnischolar_image_generate` | Text-to-image, image-to-image, or multi-reference generation |
| `omnischolar_image_edit` | Edit an existing image |
| `omnischolar_image_service` | Run supported provider status, model, or task operations |
| `ai4scholar_figure` | Generate, edit, or vectorize through Ai4Scholar |

Model selection uses the user's explicit model first, then catalog models with confirmed capabilities, then official-documentation-verified built-in models, then explicitly configured model contracts. If the model is omitted, the tool discovers and selects the newest usable model. Providers without a model catalog use a small verified built-in set and still allow `models` to override or extend the declarations.

Common tool parameters include `size`, `aspectRatio`, `resolution`, `background`, `outputFormat`, `quality`, `n`, `negativePrompt`, and `seed`. The tool maps them to each provider's protocol and returns `parameter_unsupported` before submission when a combination is not supported.

## Example config

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
        "baseUrl": "https://your-workspace.ap-southeast-1.maas.aliyuncs.com/api/v1",
        "models": {},
        "options": {
          "workspace": "your-workspace",
          "region": "ap-southeast-1",
          "protocol": "native"
        }
      }
    }
  }
}
```

Qwen AI Platform image models use the native DashScope API. Set `region` to `cn-beijing` for China (Beijing) or `ap-southeast-1` for Singapore, or provide the matching `baseUrl` directly. `protocol` defaults to `native`; set it to `openai-compatible` only when that protocol is explicitly supported. The built-in set includes `qwen-image-3.0-pro`, `qwen-image-3.0`, `wan2.7-image-pro`, `wan2.7-image`, and `z-image-turbo`; the current Qwen Image 3.0 recommendation is `qwen-image-3.0-pro`, while actual entitlement remains account- and region-dependent.

Vertex AI can use a service-account JSON file:

```json
{
  "vertex": {
    "enabled": true,
    "credentialsFile": "F:/path/to/service-account.json",
    "project": "your-project",
    "location": "global",
    "models": {
      "imagen-3.0-capability-001": {
        "capabilities": ["text-to-image", "image-to-image", "edit"]
      }
    }
  }
}
```

The service-account file is used locally to obtain an OAuth token and is never written to output artifacts. Model availability depends on project permissions, location, and model publication status.

Atlas, fal, Vertex, and DashScope/Qwen expose different catalog capabilities. Atlas, fal, Vertex, and DashScope/Qwen have small built-in model sets checked against official documentation; custom services still need an exact `baseUrl`, model ID, capability list, and generation or edit endpoint. Do not infer capabilities from the model name or treat a built-in model as an entitlement guarantee.

## Generate and edit

Before submitting a task, define the scientific content, labels, units, aspect ratio, and file format. Once the image provider key is configured, generation and reference-image upload are directly available.

Upload only images you may share with the selected service. After files are saved, signed URLs and base64 source data are removed from the returned payload. Downloads are checked for public HTTPS, file size, MIME type, and image signature. If one file in a multi-file result is missing, the incomplete set is not published.

## Current provider notes

- fal has been tested for queue submission, polling, data-URI results, text-to-image, and two-reference editing. If the local machine cannot resolve the fal CDN, a data-URI result can still be saved.
- DashScope/Qwen supports the Qwen AI Platform native endpoint `https://dashscope.aliyuncs.com/api/v1` and regional Bailian workspace endpoints such as `https://<workspace>.cn-beijing.maas.aliyuncs.com/api/v1`. When `workspace` and `region` are supplied, the tool can derive the regional endpoint.
- Gemini's `apiKeyEnv` must name an environment variable that exists.
- Atlas Cloud uses `https://api.atlascloud.ai/api/v1`, submits to `model/generateImage`, and polls `model/prediction/{id}`. The built-in set includes official Nano Banana 2, GPT Image 2, and GPT Image 2.5 Flare/Sunburst IDs. Atlas image tasks are asynchronous and their `outputs` are saved locally.
- Custom services need a working endpoint and model description.

Review text, structures, mechanisms, scale, and quantitative labels after generation. **AI images are illustrative drafts, not experimental data, real measurements, or scientific conclusions.**
