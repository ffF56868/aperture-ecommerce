# 第六步：受控售后执行与人工确认

本步把售后 Agent 从“查询和解释”扩展为“可发起、但不越权执行”的售后闭环。聊天页位于 `/after-sales`。

## 用户可见流程

1. 用户在聊天中描述退款、退货退款或取消待支付订单的诉求。
2. Agent 先核验当前用户自己的订单、订单状态和售后原因。
3. Agent 只能生成一张有效期 10 分钟的确认卡，不能直接取消订单或退款。
4. 用户在右侧“售后处理”区点击“确认提交”后：
   - 退款、退货退款会创建一条状态为“待人工审核”的售后工单。
   - 待支付订单会调用既有订单服务取消，并恢复已预留的库存。
5. 用户点击“取消”或确认卡过期时，不会产生订单状态变更或售后工单。

质量问题、物流异常和转人工属于受控低风险操作：满足订单规则后，Agent 可以创建工单，但不能给出“已退款”“已审核通过”等承诺。

## 新增接口

- `GET /api/v1/after-sales/cases/`：查询当前用户最近的售后工单。
- `POST /api/v1/after-sales/confirmations/<confirmation_id>/confirm/`：用户显式确认并执行一条待确认申请。
- `POST /api/v1/after-sales/confirmations/<confirmation_id>/reject/`：用户取消一条待确认申请。

会话发送和会话详情接口现在都会额外返回：

- `pending_confirmation`：当前会话有效的待确认申请，或 `null`。
- `recent_cases`：当前用户最近的售后工单。

## 安全与可靠性

- 所有模型工具仍是白名单工具，并对参数执行严格 JSON Schema 校验。
- 模型写权限仅能生成确认申请或创建三类受控工单，不能直接执行订单、支付或退款状态变更。
- 确认执行接口只接受登录用户本人访问；其他用户会得到 404。
- 确认执行使用数据库事务和行锁；重复点击同一确认申请不会重复创建工单。
- 取消订单复用现有事务服务，订单状态和库存恢复要么一起成功，要么一起回滚。
- Agent 工具调用和用户确认执行都会留下脱敏审计记录；错误不返回内部堆栈或密钥。

## 验证结果

- `python manage.py test apps.after_sales`：31 项通过。
- `python manage.py check`：通过。
- `python manage.py makemigrations --check --dry-run`：无待生成迁移。
- 前端 `npm run lint`、`npm run test`、`npm run build`：通过。
