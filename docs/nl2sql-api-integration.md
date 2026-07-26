# Atlas 数据洞察：AI API 接入说明

当前 `/insights/` 是前端交互演示，不会调用模型、执行 SQL 或持久化问题。页面将所有查询集中到
`experiment_app/static/app/js/insights.js` 的 `queryInsights()` 函数，后续接入时不需要重做界面。

## 推荐的数据流

```text
浏览器 → Atlas Django API → AI 模型 API
                    ↓
             受控只读查询服务 → Atlas database
                    ↓
浏览器 ← 洞察、SQL、表格结果
```

模型 API Key 只能配置在 Atlas 服务端环境中。浏览器不得直接调用模型供应商，否则密钥和内部数据结构会暴露给用户。

## 前端与 Atlas 后端的接口

实现登录保护的 `POST /api/insights/query/`，请求体：

```json
{
  "question": "PCA001 项目今年 4–6 月制备的电芯，第一圈克容量相比 1–3 月有什么变化？",
  "conversation": [
    {"question": "历史上使用 GM001 原材料制备了多少电芯？"}
  ]
}
```

成功响应：

```json
{
  "answer": "PCA001 在 4–6 月的首圈克容量均值较 1–3 月提升 2.9%。",
  "sql": "SELECT ... WHERE pc.group_id = :research_group_id LIMIT 100",
  "columns": [
    {"key": "period", "label": "对比周期"},
    {"key": "capacity", "label": "平均克容量"}
  ],
  "rows": [
    {"period": "2026 年 4–6 月", "capacity": "181.9 mAh/g"}
  ],
  "visualizations": [
    {
      "kind": "line",
      "title": "PCA001 月度首圈克容量均值",
      "x_axis": "制备月份",
      "y_axis": "首圈克容量 (mAh/g)",
      "categories": ["1 月", "2 月", "3 月", "4 月", "5 月", "6 月"],
      "summary": "月度首圈克容量从 1 月的 176.1 mAh/g 上升至 6 月的 184.2 mAh/g。",
      "series": [
        {
          "name": "PCA001",
          "unit": "mAh/g",
          "color": "#2f66d0",
          "data": [176.1, 176.9, 177.4, 179.8, 181.7, 184.2]
        }
      ]
    }
  ],
  "metadata": {
    "row_count": 1,
    "truncated": false,
    "scope": "当前 Team",
    "source": "模拟电化学数据"
  }
}
```

`visualizations` 是可选数组。当前前端支持 `line` 和 `bar`；所有图表必须提供单位和文本 `summary`，
保证表格仍是数据事实来源，并为无法读取 SVG 的用户提供等价摘要。

错误响应使用稳定的错误代码，不把模型提示词、数据库异常或敏感字段返回浏览器：

```json
{
  "error": {
    "code": "QUERY_NOT_ALLOWED",
    "message": "该问题无法转换为允许的只读分析。"
  }
}
```

接口完成后，将页面根元素的 `data-query-mode` 从 `mock` 改为 `api`；`queryInsights()` 已包含同源
`fetch`、CSRF 和错误处理逻辑。

## 模型适配层

在 Django 服务端定义供应商无关的模型适配接口，例如：

```python
class InsightsModelAdapter:
    def create_query_plan(self, question, schema, context):
        """Return a validated structured query plan, not executable free-form text."""
```

OpenAI、Azure OpenAI 或本地模型分别实现该接口。给模型的上下文应是经过筛选的业务语义结构，包括可查询实体、字段说明、关系、枚举值和用户可见范围，不要发送数据库凭据或无关实验内容。

推荐让模型返回结构化查询计划，由 Atlas 编译成只读 SQL；不要直接执行模型生成的任意 SQL。若未来确实接收 SQL，仍须经过独立的解析和验证层。

## 建议的电化学分析视图

当前 Atlas 只保存电芯标识与实验谱系，不保存首圈或循环测试结果。接入测试数据库时，建议在只读分析层建立以下受控视图，而不是让模型直接探索测试系统原始表：

- `analytics_cell_material_genealogy`：将电芯 Barcode 展平到所属 Team、项目和正负极原材料，来源于 Atlas 步骤谱系。
- `analytics_cell_first_cycle_metric`：每颗电芯的测试日期、首圈充放电克容量和首圈效率。
- `analytics_cell_cycle_result`：每颗电芯按圈次归一化的放电容量与容量保持率。

三个视图都必须包含或可可靠关联 Team 范围；跨系统关联优先使用不可变的 Cell Barcode。单位需要在进入分析视图前标准化，避免模型混合 `Ah`、`mAh`、`mAh/g` 或不同活性物质量口径。

## 服务端安全要求

- 普通用户的查询必须强制限定到 `request.user.profile.research_group_id`；不能依赖模型自行添加 Team 条件。
- Staff/superuser 的跨 Team 查询应显式选择范围，并记录实际范围。
- 仅允许 `SELECT` 和经过批准的表、字段、聚合及连接关系。
- 禁止多语句、注释绕过、子查询访问未授权表以及写入型 CTE。
- 设置最大返回行数、执行超时和结果大小；响应中声明是否截断。
- 使用只读数据库连接或只读数据库账户作为第二层保护。
- 记录用户、问题、生成计划、最终 SQL、范围、耗时、结果行数和失败原因，但不要记录返回的完整敏感数据。
- 在将数据库错误返回客户端前进行脱敏。

## 切换到真实模型的实施顺序

1. 实现模型适配接口和一个供应商适配器，通过服务端环境变量配置 API 地址、模型名与密钥。
2. 建立 Atlas 业务语义 schema，并实现结构化查询计划校验器。
3. 用 Django ORM 或受控 SQL 编译器生成查询，并在服务端注入 Team 范围和 `LIMIT`。
4. 实现 `/api/insights/query/`，返回本文约定的响应结构。
5. 添加越权、危险查询、超时、模型不可用和大结果集测试。
6. 将前端切换到 `api` 模式，先对 staff 灰度，再开放给普通工程师。
