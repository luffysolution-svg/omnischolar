# OmniScholar 项目记忆

> 维护者发布与安装排障记录。不要在此文件写入 API key、访问令牌、个人配置路径中的敏感内容或私有凭据。

## 项目基本信息

- GitHub：`luffysolution-svg/omnischolar`
- Python 包：`luffysolution-omnischolar`
- npm 包：`@luffysolution/omnischolar-pi`
- 默认分支：`main`
- 发布工作流：`.github/workflows/publish-npm.yml`
- 当前已验证版本：`0.5.1`

## 发布前检查

每次发布前先确认工作区干净、目标版本没有被使用：

```powershell
git status --short
python scripts/check_release_versions.py
```

执行完整验证：

```powershell
$env:PYTHONPATH = "src"
uv run pytest -q
uv run ruff check src tests scripts
npm test
npm run check
python C:\Users\Administrator\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
git diff --check
```

版本必须通过 `scripts/check_release_versions.py`，不要手动只改一个版本文件。

## 版本同步

使用脚本同步 Python、npm、Codex、Claude、Cursor、Pi、MCP Server 和锁文件中的版本：

```powershell
python scripts/bump_version.py 0.1.X
```

脚本会更新并校验这些发布面：

- `pyproject.toml`
- `src/omnischolar/version.py`
- `package.json`、`package-lock.json`
- `plugin.json`
- `.codex-plugin/plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `server.json`
- `pi-extension/src/index.ts`
- `uv.lock`

`mcp.json`、`.mcp.json` 和插件生成的 MCP 配置不写固定版本号；必须使用下面的刷新命令，避免 uv 使用旧缓存。

## 发布流程

1. 修改源码、文档、示例配置和测试。
2. 运行发布前检查与完整验证。
3. 执行 `python scripts/bump_version.py <新版本>`。
4. 再运行完整验证，确认所有版本一致。
5. 提交并推送 `main`：

   ```powershell
   git add <本次修改文件>
   git commit -m "<type>: <summary>"
   git push origin main
   ```

6. 创建并推送版本标签：

   ```powershell
   git tag v<新版本>
   git push origin v<新版本>
   ```

7. 查看发布工作流：

   ```powershell
   gh run list --repo luffysolution-svg/omnischolar --limit 3
   gh run watch <run-id> --repo luffysolution-svg/omnischolar --exit-status
   ```

8. 三个任务都成功后核对公开版本：

   ```powershell
   npm view @luffysolution/omnischolar-pi dist-tags.latest --prefer-online
   uv run python -c "import json, urllib.request; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/luffysolution-omnischolar/json'))['info']['version'])"
   uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar --version
   ```

PyPI 和 npm 发布后可能短暂处于处理或 CDN 传播状态；工作流成功但 registry 仍显示旧版本时，等待后重新查询，不要立即重复发布同一版本。

## Trusted Publisher 配置

发布工作流需要 GitHub Actions OIDC：

- PyPI 项目：`luffysolution-omnischolar`
- npm 项目：`@luffysolution/omnischolar-pi`
- GitHub owner：`luffysolution-svg`
- Repository：`omnischolar`
- Workflow：`publish-npm.yml`
- GitHub Actions 权限：`contents: write`、`id-token: write`

如果 PyPI 项目仍显示 pending publisher，检查 owner、repository 和 workflow filename 是否完全匹配。npm 发布使用 `--provenance`，workflow 已处理同版本已存在和并发发布的情况。

## MCP 启动与缓存规则

所有 MCP 启动配置必须使用：

```text
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```

同步修改以下位置：

- `mcp.json`
- `.mcp.json`
- `src/omnischolar/hosts/installer.py` 的 `LATEST_MCP_PROCESS`
- OpenCode 的命令数组
- `pi-extension/src/index.ts`
- README 和 `docs/INSTALLATION*.md`

只写 `uvx --from ...@latest` 可能继续使用 uv 本地缓存，不适合作为“每次安装/启动都取最新版本”的默认命令。

## 各宿主更新命令

### Python CLI

首次安装或强制刷新：

```powershell
uv tool install --reinstall luffysolution-omnischolar
```

更新和卸载：

```powershell
uv tool upgrade luffysolution-omnischolar
uv tool uninstall luffysolution-omnischolar
```

如果必须确认指定版本：

```powershell
uv tool install --reinstall luffysolution-omnischolar==<版本>
```

不要把两个命令粘连成类似 `uv tool upgrade ...uv tool upgrade ...` 的一行。

### Codex Plugin

当前 Codex CLI 没有 `codex plugin update` 子命令。更新已安装插件必须执行：

```powershell
codex plugin marketplace upgrade omnischolar
codex plugin remove omnischolar@omnischolar
codex plugin add omnischolar@omnischolar
```

核对版本：

```powershell
codex plugin list
```

期望看到版本化缓存路径类似：

```text
C:\Users\<user>\.codex\plugins\cache\omnischolar\omnischolar\<version>
```

如果 Marketplace 已从其他来源添加，先查看现有来源；不要重复添加同名但不同来源的 Marketplace。

### Claude Code

```powershell
claude plugin marketplace update omnischolar
claude plugin update omnischolar@omnischolar --scope user
```

### Pi

```powershell
pi install npm:@luffysolution/omnischolar-pi
pi update npm:@luffysolution/omnischolar-pi
pi remove npm:@luffysolution/omnischolar-pi
```

### 独立 Skills CLI

插件已经包含 Skills；需要单独安装时使用：

```powershell
npx skills add luffysolution-svg/omnischolar --skill '*' --agent codex --global --yes
npx skills update --global --yes
npx skills remove --skill '*' --agent codex --global --yes
```

## 配置规则

程序只选择一个配置源，不合并多份配置。优先级为：显式 `--config`、`OMNISCHOLAR_CONFIG`、当前项目配置、用户配置、内置默认值。

用户配置文件由 `platformdirs` 决定：

- Windows：`%LOCALAPPDATA%\omnischolar\omnischolar.config.json`
- Linux：`~/.config/omnischolar/omnischolar.config.json`
- macOS：`~/Library/Application Support/omnischolar/omnischolar.config.json`

首次启动只在没有可发现配置时创建模板，不覆盖已有配置。项目不读取旧版嵌套配置路径。

直接填写 key：

```json
{
  "apiKey": "真实 API key",
  "apiKeyEnv": null
}
```

环境变量方式：

```json
{
  "apiKey": null,
  "apiKeyEnv": "OMNISCHOLAR_MINERU_API_KEY"
}
```

`apiKeyEnv` 只能填写合法的环境变量名，不能填写真实 API key。`apiKey` 有值时优先使用 `apiKey`。

默认 provider 和工具组均启用；没有凭据的服务不会自动发起请求。不要把真实 key 写进 `mcp.json`、插件 manifest、README、测试或 Git 提交。

## 当前典型故障

### `invalid_env_name`

通常表示用户把真实 API key 填进了 `apiKeyEnv`。将同一个 key 移到 `apiKey`，并将 `apiKeyEnv` 设为 `null`；或者清空 `apiKey`，将 `apiKeyEnv` 改成合法变量名后在系统中设置该变量。

### MCP 未加载

按顺序检查：

1. `omnischolar --version`
2. `omnischolar status`
3. `uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar --version`
4. `codex plugin list` 或对应宿主的插件状态
5. 重启宿主应用，让新的环境变量和插件缓存生效

使用干净配置启动 MCP 做握手验证；当前基线应能列出 39 个工具。

## 安全与发布注意事项

- 配置文件已被 Git 忽略；不要通过 `git diff`、日志或错误信息输出 key。
- `omnischolar status` 只显示凭据是否配置及来源，不显示 key；不要恢复绝对配置路径输出。
- Zotero 仅使用本机 loopback API；本地文件读写仍受 workspace/output 根目录限制。
- 每次变更配置解析、MCP 启动、宿主安装器或发布脚本后，至少运行相关测试和 `ruff`/TypeScript 检查。
- 修改插件结构或 Marketplace 时，运行 `plugin-creator` 的 `validate_plugin.py`。
- 发布前检查 `git status --short`，确认没有 `.env`、真实配置、构建临时文件或用户数据。
