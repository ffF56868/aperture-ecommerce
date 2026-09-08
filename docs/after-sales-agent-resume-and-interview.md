# 电商售后 Agent：简历项目经历与面试准备

> 本文只记录当前仓库中已经实现、能够从代码或测试中验证的能力。没有实现的能力会明确标注，避免把规划内容误写成项目成果。

## 一、简历项目经历版

### 项目名称

电商售后智能 Agent 与售后工单工作台

### 项目介绍

面向电商售后场景，构建集订单查询、售后规则咨询、退货/退款工单创建、人工审核和通知于一体的智能客服系统。Agent 通过 OpenAI Responses API 的 Function Calling 访问受控业务工具，结合 PostgreSQL/pgvector 与 Milvus 检索售后规则，并用人工确认、权限校验、事务幂等和全链路审计保证高风险售后操作可控、可追溯。

### 技术栈

`Python`、`Django`、`Django REST Framework`、`PostgreSQL`、`pgvector`、`Milvus`、`Redis`、`Celery`、`OpenAI Responses API`、`Function Calling`、`React`、`TypeScript`、`Docker Compose`

### 可直接写入简历的技术亮点

- 基于 OpenAI Responses API Function Calling 实现电商售后 Agent，定义订单查询、售后政策检索、历史工单查询、确认卡生成和工单创建等 7 个结构化工具，使用 JSON Schema 与 DRF Serializer 双重校验参数。
- 设计订单事实与售后规则分流机制：订单信息直接读取业务数据库，政策问题进入 RAG；检索结果携带引用来源，知识库无可靠命中时转人工，减少模型编造业务规则的风险。
- 搭建多格式售后知识库，支持 `txt`、`md`、`docx`、`pdf`、网页 URL 和后台文本；文本清洗后按中文标点优先切分，采用 520 字符片段、80 字符重叠，并对手机号、邮箱和 UUID 做脱敏后再生成向量。
- 采用 PostgreSQL/pgvector 与 Milvus 双存储：PostgreSQL 保存文档、切片、哈希和业务关联，Milvus 保存 1536 维向量；按商品、分类、全局三级范围过滤，商品规则优先，Milvus 不可用时降级到 pgvector。
- 实现售后高风险操作的人机协同：退款、退货退款和待支付订单取消只能先生成确认卡，用户确认后才进入执行接口；工具入口依次执行危险调用拦截、权限检查、Serializer 校验和业务规则校验。
- 通过 AgentRun、AgentRunEvent 和 ToolExecution 记录模型请求、工具调用、拒绝、失败、耗时、Token 和最终状态；设置最多 3 轮工具调用，连续工具失败或超出轮次自动转人工。
- 建立 20 条确定性 Agent 回放评测集，覆盖他人订单、退款确认、规则不满足、RAG 未命中、SQL 提示注入、危险参数、越权和工具循环等场景；最近一次结果为意图识别 100%、工具选择 100%、越权拦截 100%、危险操作拦截 100%、失败率 0%，平均响应时间 26 ms。

> 简历中的百分比和耗时应注明“确定性回放评测结果”，它们不是线上生产流量指标。

## 二、面试展开版

### 1. 用户请求的完整工作流程

一次售后对话的主要链路如下：

1. 用户在前端输入问题，后端创建或恢复会话，并加载最近 8 条对话消息、最多 3 条结构化客户记忆。
2. `collaboration.py` 根据消息识别本轮固定专业角色：`order_analyst`、`policy_advisor`、`case_tracker` 或 `workflow_specialist`，同时由后端生成本轮允许使用的工具集合。
3. `agent_service.py` 调用 OpenAI Responses API，并把允许的工具以 Function Calling schema 传给模型。工具调用关闭并行执行，最多执行 3 轮。
4. 如果模型返回工具调用，后端先检查工具名和参数，再检查角色权限，最后进入工具 handler、Serializer 和业务规则校验。
5. 工具结果以结构化结果回传模型，同时写入 `ToolExecution`、`AgentRunEvent` 等审计记录。模型根据结果继续回答、请求补充信息，或生成确认卡。
6. 对需要用户确认的操作，系统只返回待确认状态和确认卡，不在模型回合内直接退款、退货或取消订单。
7. 用户确认后，后端确认接口在事务中执行工单创建或状态变更，并通过幂等键避免重复提交；失败时回滚事务并记录失败原因。
8. 发生规则不满足、知识库无可靠命中、连续工具失败或模型超过调用轮次时，系统把会话转人工。

### 2. 工具定义、参数校验与结果回传

当前注册的 7 个工具是：

| 工具 | 用途 | 权限/风险 |
| --- | --- | --- |
| `list_my_orders` | 查询当前用户订单列表 | 只读 |
| `get_my_order_detail` | 查询当前用户订单详情 | 只读 |
| `list_after_sales_policies` | 查询结构化售后政策 | 只读 |
| `search_after_sales_knowledge` | 检索售后知识库 | 只读 |
| `list_my_after_sales_cases` | 查询当前用户售后工单 | 只读 |
| `prepare_after_sales_confirmation` | 生成高风险操作确认卡 | 需要确认 |
| `create_after_sales_case` | 创建售后工单 | 受保护业务操作 |

每个工具同时具备三层约束：

- OpenAI Function Calling 的 JSON Schema 限定字段、类型、枚举值和必填项。
- 后端使用 DRF Serializer 再次解析，拒绝多余字段、错误类型和不合法参数。
- handler 使用当前登录用户的身份从服务端取订单归属，不接受模型传入的用户 ID；再执行订单状态、售后类型、时间和政策条件检查。

工具结果不是直接拼接自然语言，而是返回结构化的成功、拒绝或失败信息，包括业务状态、必要字段、是否需要确认、引用来源和下一步动作。模型只能根据这些结果生成用户可见回复。

### 3. 当前的 Agent 编排方式

项目当前使用 OpenAI Responses API 的 Function Calling 编排，不使用 LangGraph。编排逻辑集中在 `agent_service.py`，工具实现位于 `tools.py`，角色路由和协作约束位于 `collaboration.py`。

当前的“多 Agent”是固定专业角色路由，而不是多个独立模型实例：

- `order_analyst`：订单查询和订单状态分析。
- `policy_advisor`：售后规则和知识库咨询。
- `case_tracker`：历史售后工单查询。
- `workflow_specialist`：售后流程、资料补充和人工转接。

角色由后端决定允许工具，模型不能通过提示词自行扩大工具权限。这种设计足以表达不同领域的职责边界，也保留了后续迁移到 LangGraph 的空间。

### 4. RAG 文档处理和切分

#### 支持的输入

知识库支持：

- `.txt`、`.md`：读取文本内容。
- `.docx`：使用 `python-docx` 提取段落。
- `.pdf`：使用 `pypdf` 提取页面文本。
- 网页 URL：使用 HTTP/HTTPS 抓取，再用 BeautifulSoup 清理 HTML 文本。
- 后台直接输入文本。

单文件最大 12 MB。网页抓取不是任意请求：系统只允许 HTTP/HTTPS，拒绝携带账号密码的 URL，并校验 DNS/IP，阻止 loopback、private、link-local、reserved 和 unspecified 地址；同时限制响应大小和重定向次数，降低 SSRF 风险。

#### 文本切分

文本会先清洗空白和无效内容，再按中文句号、感叹号、问号、分号等标点优先切分。当前参数为：

```text
CHUNK_SIZE = 520
CHUNK_OVERLAP = 80
```

切分时保留 80 字符上下文重叠，减少规则被切在句子边界后导致语义不完整的问题。每个切片保存序号、文本哈希、所属文档和商品/分类范围，便于增量更新和一致性修复。

#### Embedding 前处理

使用默认模型 `text-embedding-3-small` 生成 1536 维向量。向量化前将手机号、邮箱和 UUID 替换为占位符，避免把不必要的个人标识写入向量服务；原始业务关联仍保存在受控的业务数据库中。

### 5. PostgreSQL、pgvector 与 Milvus 如何配合

PostgreSQL 是业务事实和知识库元数据的权威来源：

- `KnowledgeDocument`：文档名称、来源、类型、处理状态、范围和错误信息。
- `KnowledgeChunk`：切片文本、序号、文本哈希、Embedding、Milvus 向量 ID 和同步状态。
- pgvector HNSW 索引：作为 PostgreSQL 内的向量检索能力和 Milvus 不可用时的回退路径。

Milvus 集合默认名为 `after_sales_knowledge`，当前字段为：

```text
id          主键
document_id 文档 ID
chunk_id    切片 ID
scope_key   GLOBAL / CATEGORY:<id> / PRODUCT:<id>
embedding   FLOAT_VECTOR，1536 维
```

索引使用 COSINE 距离和 AUTOINDEX。检索时先根据用户问题确定商品和分类范围，再按以下优先级组织候选结果：

```text
商品规则 > 分类规则 > 全局规则
```

同一范围内按相似度排序。默认 `AFTER_SALES_RAG_MAX_COSINE_DISTANCE=0.55`，只有达到最低相似度要求的结果才会作为可靠知识返回。Milvus 连接失败时回退到 PostgreSQL pgvector，并把知识库状态标记为“已降级（PostgreSQL）”，而不是误报为完全就绪。

### 6. 索引一致性和知识库更新

文档、切片和向量采用可追踪 ID 与哈希关联。重复导入时可根据内容哈希复用或更新切片；处理失败时记录文档错误状态，避免半成品被当作可检索知识。

项目提供一致性修复命令：

```powershell
docker compose exec backend python manage.py repair_after_sales_knowledge
```

此前实际验证结果为 12 篇文档、12 个 PostgreSQL 切片、12 条 Milvus 向量，0 个孤儿向量，0 个异常文档状态。面试时可以把它作为“元数据和向量库一致性治理”的具体证据。

### 7. 检索引用、未命中与事实边界

RAG 返回切片文本、来源名称、来源类型和文档标识，Agent 回复中可以显示引用来源。售后规则问题如果没有达到相似度阈值，会明确返回无法确认并转人工。

订单号、订单状态、商品、金额和用户归属属于业务事实，必须通过订单工具读取，不能由 RAG 推断。这样可以把“知识性回答”和“实时业务数据”隔离开。

当前实现没有 BM25，也没有 BM25 与向量检索的混合排序，因此简历中不应写“BM25 融合”“RRF”或“混合召回效果提升”。当前也没有独立的 RAG Recall@K、MRR 或 nDCG 测试集，所以不写未经测量的召回率数字。

### 8. 工具权限与危险调用控制

工具执行前的安全检查包括：

- 工具名黑名单：拦截 SQL、database、shell、command、subprocess、terminal、powershell、bash、filesystem、HTTP、fetch、webhook、browser、curl、payment 等危险能力。
- 参数键黑名单：拦截 `sql`、`query`、`command`、`script`、`shell`、`path`、`file`、`url`、`endpoint`、`token`、`secret`、`api_key`、`password` 等字段。
- 权限分级：只读工具、需要确认的工具和受保护业务工具分开处理。
- 身份和归属校验：服务端以登录用户身份查询订单，阻止模型越权访问其他用户数据。
- 日志脱敏：审计日志中的敏感参数不会原样保存。

项目没有开放任意 Python、Shell、SQL、文件或代码执行工具，因此目前不是“实现了代码执行沙箱”，而是通过不提供此类工具并在工具入口拦截危险调用，降低提示注入导致的执行风险。

### 9. 人工确认、状态管理、幂等与回滚

退款、退货退款和待支付订单取消属于高风险操作。模型只能调用 `prepare_after_sales_confirmation` 生成确认卡，用户明确确认后，服务端确认接口才执行后续操作。

会话和工单会记录活动、等待确认、已转人工、已解决、失败等状态。工单创建在数据库事务中完成，并使用幂等控制避免重复创建；执行失败会回滚数据库变更，同时保留 AgentRunEvent 和 ToolExecution 失败记录，便于追踪。

连续两次相同工具失败或工具调用超过 3 轮后，系统停止继续尝试并转人工，避免模型在异常状态下无限重试。

### 10. Memory 的实际实现

上下文不是无限拼接历史消息，而是采用有限窗口：每轮注入最近 8 条用户/助手消息，以及最多 3 条结构化 `CustomerMemory`。记忆用于保存与售后处理有关的稳定信息，订单和支付等实时事实仍以业务工具查询结果为准，避免过期记忆覆盖数据库状态。

### 11. Agent 全链路日志与可观测性

管理员可以查看 Agent 运行链路。当前记录内容包括：

- AgentRun：会话、用户、模型请求、开始/结束时间、总耗时、Token、最终状态。
- AgentRunEvent：模型请求、模型响应、工具调用、工具结果、拒绝、失败和转人工等事件。
- ToolExecution：工具名、参数摘要、结果状态、耗时、错误信息和脱敏后的审计数据。

因此可以回答“模型为什么调用这个工具”“工具被谁拒绝”“耗时发生在哪一段”“为什么转人工”等面试问题。当前属于应用内数据库审计和后台查看能力，不应描述成已经接入 Prometheus、Grafana 或 OpenTelemetry。

### 12. Agent Eval 评测证据

当前评测位于 `backend/apps/after_sales/evaluation.py`，配套说明和报告位于 `docs/after-sales-agent-eval.md`、`docs/after-sales-agent-eval-report.md`。

评测集包含 20 条确定性回放案例，覆盖：

- 正常订单查询、订单详情和历史工单查询。
- 退款、退货退款、待支付取消的确认流程。
- 不满足政策条件的退款或取消。
- 质量问题、物流异常工单创建。
- RAG 命中并返回引用、RAG 无可靠命中并转人工。
- 查询他人订单、SQL 提示注入、直接退款、危险 endpoint 参数。
- 多余 schema 字段、角色权限拒绝、连续工具失败和工具轮次超限。

评测不调用真实模型，避免受模型随机性和 API 费用影响；但复用了真实的工具 schema、权限、安全、订单归属、RAG 兜底和审计链路。外层事务会回滚临时测试数据。

最近一次报告：

| 指标 | 结果 |
| --- | ---: |
| 意图识别 | 100.0%（20/20） |
| 工具选择 | 100.0%（20/20） |
| 工具参数 | 100.0%（15/15） |
| 越权拦截 | 100.0%（3/3） |
| 危险操作拦截 | 100.0%（3/3） |
| 人工转接率 | 10.0%（2/20） |
| 失败率 | 0.0%（0/20） |
| 平均响应时间 | 26 ms |

这里的人工转接率是测试集中的预期转人工比例，不代表线上客服转人工率；平均响应时间是本地确定性回放耗时，不代表包含真实大模型网络请求的生产延迟。

### 13. 可验证命令

在项目目录执行：

```powershell
# Django 配置检查
docker compose exec backend python manage.py check

# 知识库一致性修复/检查
docker compose exec backend python manage.py repair_after_sales_knowledge

# 后端知识库测试
docker compose exec backend python manage.py test apps.after_sales.tests.test_knowledge

# 前端检查
cd frontend
npm run lint
npm run build
```

评测报告中的 20 条回放案例可按项目现有文档说明执行。验证时应保留命令输出和报告时间，面试时说明测试环境、数据范围和指标口径。

## 三、一分钟面试介绍

我做的是一个电商售后 Agent，重点不是简单接一个聊天窗口，而是把模型接入真实的订单和售后流程。Agent 使用 Responses API 的 Function Calling 调用 7 个受控工具，订单事实通过业务数据库查询，售后政策通过支持多种文档格式的 RAG 检索。知识库采用 PostgreSQL/pgvector 加 Milvus 双存储，按商品、分类和全局范围做规则优先级检索，Milvus 不可用时可以降级到 pgvector。

在安全上，我把工具分成只读、需要确认和受保护操作三类，模型不能直接退款、取消订单或访问他人订单。高风险动作必须先生成确认卡，再由用户确认，后端执行身份校验、参数校验、政策校验、幂等和事务回滚；同时对 SQL、Shell、文件、URL 等危险工具名和参数做拦截。项目还记录 AgentRun、工具调用和失败事件，并准备了 20 条确定性评测案例，验证意图、工具选择、越权拦截、危险调用拦截和失败转人工等能力。

## 四、当前边界和可作为后续规划的内容

以下内容当前没有实现，不应写成已完成：

- BM25 或 BM25 + 向量的混合检索。
- LangGraph 工作流编排。
- 任意 Python、Shell、SQL 或文件执行沙箱。
- 独立的 RAG Recall@K、MRR、nDCG 评测及其提升数字。
- Prometheus、Grafana、OpenTelemetry 等外部可观测性平台。

如果面试官追问后续方向，可以说明：下一步会在现有 `search_after_sales_knowledge` 边界内增加 BM25 和向量召回的融合评测，并补充带人工标注答案的 Recall@K/MRR 数据；当节点状态、分支和重试策略继续复杂化时，再评估把当前编排迁移为 LangGraph，而不是为了使用框架而使用框架。
