# 售后 Agent 知识库（RAG）

## 职责边界

RAG 只回答经过审核的、非实时的售后知识：退款流程说明、尺码建议、面料洗护、物流异常说明和人工服务规则。

下列事实不允许使用 RAG 判断，必须调用受控业务工具或由人工处理：订单归属、支付状态、发货状态、退款执行、订单取消和工单审核。

## 实现结构

- `KnowledgeDocument`：后台可维护的可信知识文档，支持直接文本、`.txt`、`.md`、`.docx`（Word）、`.pdf` 和网页 URL。
- `KnowledgeChunk`：文档按中文语义边界切分后保存的文本、引用信息和稳定向量 ID。
- Milvus：默认保存和检索向量；PostgreSQL `pgvector` 作为可选备用检索，避免 Milvus 暂时不可用时中断售后服务。
- `search_after_sales_knowledge`：只读、schema 严格、权限受限并写入工具审计的 Agent 工具。
- OpenAI `text-embedding-3-small`：默认 1536 维，API Key 仅保存在后端环境变量。

每次检索会附带来源名称。相似度没有达到 `AFTER_SALES_RAG_MAX_COSINE_DISTANCE` 时，后端不会让模型继续猜测，而是自动创建一条“人工服务”工单。

## 初始化与维护

在 Docker 服务已启动且 `backend/.env` 中有 `OPENAI_API_KEY` 后运行：

```powershell
docker compose exec backend python manage.py seed_after_sales_knowledge
```

该命令会导入 12 篇中文初始知识，并只为新增或变更的切片调用 Embedding。需要强制重建全部向量时：

```powershell
docker compose exec backend python manage.py seed_after_sales_knowledge --force
```

管理员登录网站后打开 `/staff/knowledge-base`，即可上传文档、读取网页、输入文本、搜索文档、启停检索、重建索引和删除来源。上传请求会先解析并保存来源，随后由 Celery 异步分块、Embedding 并写入 Milvus；页面上的“已就绪”表示可以被 Agent 检索。页面中的“检索测试”可以直接输入问题，查看命中的切片、相似度、文档名称和引用来源，并验证商品/分类专属规则。

也可以在 Django Admin 的“售后知识文档”中查看文档和切片。每篇文档可选全局规则、指定商品分类或指定商品；检索时 Agent 可以传入商品/分类范围，优先匹配专属规则，同时保留全局规则。

如果 Milvus 暂不可用，默认会回退到 PostgreSQL `pgvector`，页面会保留提示。需要强制要求 Milvus 可用时，将 `AFTER_SALES_ALLOW_POSTGRES_FALLBACK=False`。

## 手工验收

1. 以普通用户登录，进入 `/after-sales`。
2. 发送“衣服尺码怎么选”或“深色衣服怎么洗”。
3. 回复应基于知识库，并在末尾看到“参考知识库：...”。
4. 发送一个知识库明显没有覆盖的问题，例如“这件衣服能不能防电磁波”。
5. 页面应显示已转人工和工单号；客服工作台会出现“人工服务”工单。
6. 发送“我的订单是否已发货”。Agent 应查询订单，不应只根据知识库回答。
7. 管理员在知识库页面的“检索测试”中输入问题，应能看到切片正文、相似度和引用来源；选择商品或分类后，应优先检索对应范围的规则。

## 配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding 模型 |
| `OPENAI_EMBEDDING_DIMENSIONS` | `1536` | 与当前向量字段一致，不能随意修改 |
| `AFTER_SALES_RAG_MAX_COSINE_DISTANCE` | `0.55` | 余弦距离阈值，越小越严格 |
| `AFTER_SALES_VECTOR_BACKEND` | `milvus` | 向量后端；可设为 `postgres` 关闭 Milvus |
| `AFTER_SALES_ALLOW_POSTGRES_FALLBACK` | `True` | Milvus 不可用时是否回退 PostgreSQL |
| `MILVUS_URI` | `http://milvus:19530` | Milvus 地址 |
| `MILVUS_COLLECTION` | `after_sales_knowledge` | 向量集合名 |
| `KNOWLEDGE_WEB_TIMEOUT_SECONDS` | `15` | 网页来源读取超时 |

## 管理接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/after-sales/staff/knowledge-documents/` | 管理员查看文档和索引状态 |
| POST | `/api/v1/after-sales/staff/knowledge-documents/` | 管理员上传文本、文件或网页来源 |
| POST | `/api/v1/after-sales/staff/knowledge-documents/search/` | 管理员测试检索并查看引用切片 |
| GET/PATCH/DELETE | `/api/v1/after-sales/staff/knowledge-documents/{id}/` | 查看、更新或删除文档 |
| POST | `/api/v1/after-sales/staff/knowledge-documents/{id}/reindex/` | 强制重建索引 |
