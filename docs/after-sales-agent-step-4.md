# 电商售后 Agent：第四步 OpenAI 接入准备

## 本步完成内容

本步接入官方 OpenAI Python SDK，并完成模型调用前的安全边界。暂时不创建聊天接口，也不发出任何模型请求；第五步会接入 Responses API 的对话和工具调用循环。

已注册给模型的只读工具只有三个：

| 工具名 | 作用 | 权限限制 |
| --- | --- | --- |
| `list_my_orders` | 查询当前用户最近 10 笔订单 | 仅当前登录用户 |
| `get_my_order_detail` | 查询指定订单详情 | 仅当前登录用户；订单号不属于本人时返回未找到 |
| `list_after_sales_policies` | 查询售后规则 | 只读 |

所有工具参数都使用 JSON Schema 严格校验，拒绝额外字段。工具名不在白名单时，例如 `run_sql`、Shell、文件操作或任意 HTTP 请求，会被直接拒绝，并把脱敏参数、结果和耗时写进 `ToolExecution` 审计日志。

退款、取消订单、创建工单等写操作仍未暴露给模型。后续步骤会先创建确认请求，只有用户在页面明确确认后，后端才会在数据库事务中执行受控写操作。

## 配置自己的 OpenAI API Key

在 `backend/.env` 填入自己的 Key，保留等号，值写在等号后面：

```text
OPENAI_API_KEY=你的_OpenAI_API_Key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_REQUEST_TIMEOUT_SECONDS=30
```

Key 只能存在于本机的 `backend/.env`。不要填到网页、前端代码、截图或聊天消息中。`backend/.env.example` 只保留空 Key，便于以后部署时参考。

修改依赖或环境变量后，在项目根目录运行：

```powershell
docker compose build backend celery_worker celery_beat
docker compose up -d --no-deps backend celery_worker celery_beat
```

## 验收

本步的后端测试会验证：

1. 工具定义只包含白名单工具，并且全部启用严格参数 Schema。
2. 订单工具永远只返回当前用户自己的订单。
3. 非本人订单返回安全的 `ORDER_NOT_FOUND`，不会泄漏订单信息。
4. 未注册工具和权限不足工具都会被拒绝并写审计日志。
5. 没有配置 API Key 时，在发起网络请求前就会给出清晰的配置错误。
