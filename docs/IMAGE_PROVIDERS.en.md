# Scientific image services

[简体中文](IMAGE_PROVIDERS.md)

OmniScholar can connect to OpenAI, xAI, Gemini, Vertex AI, fal.ai, DashScope/Qwen, Atlas, and custom OpenAI-compatible services. Available models depend on the account, region, endpoint, and configuration.

## Tools

| Tool | Use |
|---|---|
| `omnischolar_image_models` | Show configured models and their usable operations |
| `omnischolar_image_generate` | Text-to-image, image-to-image, or multi-reference generation |
| `omnischolar_image_edit` | Edit an existing image |
| `omnischolar_image_service` | Run supported provider status, model, or task operations |
| `ai4scholar_figure` | Generate, edit, or vectorize through Ai4Scholar |

Each model must explicitly declare the operation it supports. A model name appearing in a provider catalog does not by itself prove that it can generate or edit images; the corresponding operation must show `usable: true` in `omnischolar_image_models`.

## Example config

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

A custom service needs an exact `baseUrl`, model ID, capability list, and generation or edit endpoint. Do not infer capabilities from the model name.

## Generate and edit

Before submitting a task, define the scientific content, labels, units, aspect ratio, and file format. Generation requires `allowPaid` for that call. Uploading a reference image also requires `allowExternalUpload` for that call.

Upload only images you may share with the selected service. After files are saved, signed URLs and base64 source data are removed from the returned payload. Downloads are checked for public HTTPS, file size, MIME type, and image signature. If one file in a multi-file result is missing, the incomplete set is not published.

## Current provider notes

- fal has been tested for queue submission, polling, data-URI results, text-to-image, and two-reference editing. If the local machine cannot resolve the fal CDN, a data-URI result can still be saved.
- DashScope/Qwen currently needs a workspace-scoped endpoint or an explicit `baseUrl` supplied by the provider. A retired generic endpoint returns `dashscope_workspace_required`.
- Gemini's `apiKeyEnv` must name an environment variable that exists.
- Atlas and custom services need a working endpoint and model description.

Review text, structures, mechanisms, scale, and quantitative labels after generation. **AI images are illustrative drafts, not experimental data, real measurements, or scientific conclusions.**
