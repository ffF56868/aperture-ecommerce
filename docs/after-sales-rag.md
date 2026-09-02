# 售后 Agent 知识库（RAG）

## 职责边界

RAG 只回答经过审核的、非实时的售后知识：退款流程说明、尺码建议、面料洗护、物流异常说明和人工服务规则。

下列事实不允许使用 RAG 判断，必须调用受控业务工具或由人工处理：订单归属、支付状态、发货状态、退款执行、订单取消和工单审核。

## 实现结构

- `KnowledgeDocument`：后台可维护的可信知识文档。
- `KnowledgeChunk`：文档按中文语义边界切分后存储的文本和向量。
- PostgreSQL `pgvector`：使用 HNSW + cosine distance 检索最相近的切片。
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

管理员可在 Django Admin 的“售后知识文档”中查看、启停和编辑文档。编辑内容后执行一次上述命令，系统会按内容哈希只重建改动文档的向量。

## 手工验收

1. 以普通用户登录，进入 `/after-sales`。
2. 发送“衣服尺码怎么选”或“深色衣服怎么洗”。
3. 回复应基于知识库，并在末尾看到“参考知识库：...”。
4. 发送一个知识库明显没有覆盖的问题，例如“这件衣服能不能防电磁波”。
5. 页面应显示已转人工和工单号；客服工作台会出现“人工服务”工单。
6. 发送“我的订单是否已发货”。Agent 应查询订单，不应只根据知识库回答。

## 配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding 模型 |
| `OPENAI_EMBEDDING_DIMENSIONS` | `1536` | 与当前向量字段一致，不能随意修改 |
| `AFTER_SALES_RAG_MAX_COSINE_DISTANCE` | `0.55` | 余弦距离阈值，越小越严格 |
