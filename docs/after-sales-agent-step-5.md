# 第五步：接入真实模型对话

本步把 OpenAI Responses API 接入售后 Agent，并开放一个登录用户可见的中文聊天页：`/after-sales`。

## 新增接口

- `POST /api/v1/after-sales/conversations/`
  - 请求：`{"message":"帮我查询最近订单","conversation_id":"可选 UUID"}`
  - 响应：会话 ID、助手回复和本次工具调用摘要。
- `GET /api/v1/after-sales/conversations/<conversation_id>/`
  - 只允许会话所属用户读取自己的用户/助手消息。工具入参、工具结果和审计记录不会暴露给浏览器。

## 本步运行流程

1. 用户在页面发送消息，后端创建或校验该用户自己的会话。
2. 后端保存用户消息，并把有限的近期消息、会话摘要和少量结构化记忆作为上下文发送给模型。
3. 模型若需要订单事实，只能调用 `list_my_orders`、`get_my_order_detail` 或 `list_after_sales_policies`。
4. 后端校验工具 JSON Schema、用户归属和只读权限，执行结果写入 `ToolExecution` 与 `AgentMessage` 审计记录。
5. 工具结果通过 `function_call_output` 回传模型，最多继续三轮，避免无限循环。
6. 后端保存最终中文回复和可复用的短会话摘要，浏览器仅展示用户和助手消息。

## 安全边界

- 模型没有 SQL、Shell、文件、任意 HTTP 或跨用户查询能力。
- 无论模型如何要求，本步都不会退款、取消订单、创建工单或修改订单。
- API Key 仅保留在 `backend/.env`，不会返回给浏览器、日志或 API 响应。
- 模型异常和未配置情况均返回通用的 `503` 提示，不泄露内部错误。

退款、退货、取消订单、自动工单以及人工确认卡片将放在第六步实现。
