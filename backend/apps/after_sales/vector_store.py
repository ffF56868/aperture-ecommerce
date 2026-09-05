"""Milvus storage for retrieval vectors.

PostgreSQL remains the metadata and audit store. Milvus only stores vectors and
stable IDs, which makes re-indexing and source deletion explicit and auditable.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)
MILVUS_ALIAS = "after_sales"


class MilvusUnavailable(RuntimeError):
    """Milvus cannot be reached or its collection cannot be prepared."""


def _client_parts():
    try:
        from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
    except ImportError as exc:  # pragma: no cover - dependency is installed in Docker
        raise MilvusUnavailable("未安装 pymilvus。") from exc
    return Collection, CollectionSchema, DataType, FieldSchema, connections, utility


def _connect(connections) -> None:
    try:
        if connections.has_connection(MILVUS_ALIAS):
            return
    except Exception:
        pass
    kwargs: dict[str, Any] = {
        "alias": MILVUS_ALIAS,
        "uri": settings.MILVUS_URI,
        "timeout": settings.MILVUS_TIMEOUT_SECONDS,
    }
    if settings.MILVUS_TOKEN:
        kwargs["token"] = settings.MILVUS_TOKEN
    try:
        connections.connect(**kwargs)
    except Exception as exc:
        raise MilvusUnavailable("Milvus 连接失败。") from exc


def _collection():
    Collection, CollectionSchema, DataType, FieldSchema, connections, utility = _client_parts()
    _connect(connections)
    try:
        if not utility.has_collection(settings.MILVUS_COLLECTION, using=MILVUS_ALIAS):
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=140),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(name="scope_key", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=settings.OPENAI_EMBEDDING_DIMENSIONS,
                ),
            ]
            schema = CollectionSchema(fields=fields, description="售后 Agent 知识库")
            collection = Collection(
                name=settings.MILVUS_COLLECTION,
                schema=schema,
                using=MILVUS_ALIAS,
            )
            collection.create_index(
                field_name="embedding",
                index_params={
                    "index_type": "AUTOINDEX",
                    "metric_type": "COSINE",
                    "params": {},
                },
            )
        else:
            collection = Collection(settings.MILVUS_COLLECTION, using=MILVUS_ALIAS)
        collection.load(timeout=settings.MILVUS_TIMEOUT_SECONDS)
        return collection
    except Exception as exc:
        raise MilvusUnavailable("Milvus 知识库集合初始化失败。") from exc


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _scopes(document) -> list[str]:
    scopes: list[str] = []
    if document.product_id:
        scopes.append(f"PRODUCT:{document.product_id}")
    if document.product_category_id:
        scopes.append(f"CATEGORY:{document.product_category_id}")
    return scopes or ["GLOBAL"]


def delete_document_vectors(document_id: str) -> None:
    collection = _collection()
    try:
        collection.delete(expr=f'document_id == "{_escape(str(document_id))}"')
        collection.flush()
    except Exception as exc:
        raise MilvusUnavailable("Milvus 删除旧向量失败。") from exc


def upsert_document_vectors(document, chunks, embeddings: list[list[float]]) -> int:
    """Replace every vector belonging to one document; return inserted row count."""

    if len(chunks) != len(embeddings):
        raise MilvusUnavailable("向量和知识切片数量不一致。")
    collection = _collection()
    try:
        collection.delete(expr=f'document_id == "{_escape(str(document.id))}"')
        scopes = _scopes(document)
        rows = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            for scope in scopes:
                rows.append(
                    [
                        f"{chunk.id}:{scope}",
                        str(document.id),
                        str(chunk.id),
                        scope,
                        embedding,
                    ]
                )
        if rows:
            # pymilvus expects one column per schema field, not row records.
            collection.insert(
                [
                    [row[0] for row in rows],
                    [row[1] for row in rows],
                    [row[2] for row in rows],
                    [row[3] for row in rows],
                    [row[4] for row in rows],
                ]
            )
        collection.flush()
        return len(rows)
    except Exception as exc:
        raise MilvusUnavailable("Milvus 写入向量失败。") from exc


def search_vectors(query_embedding: list[float], *, scope_keys: list[str], limit: int) -> list[dict[str, Any]]:
    collection = _collection()
    escaped = [f'"{_escape(scope)}"' for scope in scope_keys]
    expr = f"scope_key in [{','.join(escaped)}]"
    try:
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {}},
            limit=max(1, limit),
            expr=expr,
            output_fields=["chunk_id", "document_id", "scope_key"],
            timeout=settings.MILVUS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        raise MilvusUnavailable("Milvus 检索失败。") from exc
    hits: list[dict[str, Any]] = []
    for hit in results[0] if results else []:
        entity = getattr(hit, "entity", None)
        chunk_id = entity.get("chunk_id") if entity else None
        if chunk_id:
            document_id = entity.get("document_id")
            scope_key = entity.get("scope_key") or "GLOBAL"
            hits.append(
                {
                    "chunk_id": str(chunk_id),
                    "document_id": str(document_id),
                    "scope_key": str(scope_key),
                    "similarity": round(max(0.0, float(hit.distance)), 3),
                }
            )
    return hits
