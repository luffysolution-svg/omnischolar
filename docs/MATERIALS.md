# 材料与化学数据

[English](MATERIALS.en.md)

## Materials Project

Materials Project 使用以下工具：

| 工具 | 用途 |
|---|---|
| `materials_capabilities` | 查看当前支持的数据类型、字段和筛选条件，不联网 |
| `materials_search` | 按化学式、元素、化学体系、稳定性等条件筛选材料概览 |
| `materials_route_search` | 查询 thermo 等专用数据集合 |
| `materials_get` | 按材料 ID 和指定数据类型获取单条记录 |
| `materials_advanced` | 获取相图数据；配置本地后端后可计算 XRD |
| `materials_export` | 将已有结果保存为 JSON、CSV、Markdown 或 CIF |

配置示例：

```json
{
  "schemaVersion": 1,
  "data": {
    "materialsProject": {
      "enabled": true,
      "apiKeyEnv": "OMNISCHOLAR_MATERIALS_PROJECT_API_KEY",
      "maxPages": 5
    }
  }
}
```

查询时要分清化学式、元素集合、化学体系、material ID 和 task ID。不同数据集合支持的筛选字段并不相同，可先调用 `materials_capabilities`。

CIF 导出只使用返回记录中的晶格和位点数据，并检查数值、占位率和坐标。导出的 P1 结构用于数据交换，不代表已经完成对称性分析。数据库计算得到的稳定性也不等同于实验可合成性。

XRD 需要额外的本地计算后端。未安装时，`materials_advanced` 会返回 `local_backend_required`，不会生成一条看似真实的衍射曲线。

## CAS Common Chemistry

当前版本只有在配置中提供服务商正式给出的接口地址和请求/响应说明文件后，才会启用 CAS 查询。仅有 API key 或网页登录权限不够。

未提供这些信息时，`chemical_sources` 会显示 `contract_blocked`，`chemical_search` 和 `chemical_get` 不会猜测接口地址。

CAS 数据仍受 CAS 的许可条款约束，其中可能包含非商业使用限制。
