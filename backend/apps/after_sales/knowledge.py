"""Trusted-document embedding, indexing and vector retrieval for the after-sales Agent."""

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Case, IntegerField, Q, When
from django.utils import timezone
from pgvector.django import CosineDistance

from apps.products.models import Product
from .knowledge_seed import KNOWLEDGE_DOCUMENTS
from .models import KnowledgeChunk, KnowledgeDocument
from .openai_client import OpenAIConfigurationError, get_openai_client
from .vector_store import MilvusUnavailable, search_vectors, upsert_document_vectors

CHUNK_SIZE = 520
CHUNK_OVERLAP = 80
DEFAULT_RESULTS = 3
MAX_RESULTS = 8
EMBEDDING_BATCH_SIZE = 64
logger = logging.getLogger(__name__)


class KnowledgeBaseError(RuntimeError):
    """A safe failure when knowledge indexing or retrieval cannot be completed."""


@dataclass(frozen=True)
class KnowledgeSearchResult:
    matches: list[dict[str, Any]]
    requires_human_escalation: bool
    message: str


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def split_knowledge_content(content: str) -> list[str]:
    """Split Chinese text into bounded, slightly overlapping retrieval chunks."""

    normalized = _normalize_text(content)
    if not normalized:
        return []
    if len(normalized) <= CHUNK_SIZE:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + CHUNK_SIZE)
        if end < len(normalized):
            boundary = max(
                normalized.rfind(marker, start + CHUNK_SIZE // 2, end)
                for marker in ("。", "！", "？", "；")
            )
            if boundary >= start + CHUNK_SIZE // 2:
                end = boundary + 1
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _embedding_text(value: str) -> str:
    """Keep obvious personal identifiers out of the embedding service request."""

    value = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[手机号]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[邮箱]", value)
    value = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "[订单标识]",
        value,
    )
    return _normalize_text(value)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Create embeddings through the configured OpenAI account, preserving input order."""

    if not texts:
        return []
    if settings.OPENAI_EMBEDDING_DIMENSIONS != 1536:
        raise KnowledgeBaseError("当前知识库向量维度与数据库模型不一致。")
    try:
        embeddings = []
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + EMBEDDING_BATCH_SIZE]
            response = get_openai_client().embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=[_embedding_text(text) for text in batch],
                dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
            )
            embeddings.extend(
                list(item.embedding)
                for item in sorted(response.data, key=lambda item: item.index)
            )
    except OpenAIConfigurationError as exc:
        raise KnowledgeBaseError("未配置知识库 Embedding 服务。") from exc
    except Exception as exc:
        raise KnowledgeBaseError("知识库 Embedding 服务暂时不可用。") from exc

    if len(embeddings) != len(texts) or any(
        len(embedding) != settings.OPENAI_EMBEDDING_DIMENSIONS for embedding in embeddings
    ):
        raise KnowledgeBaseError("知识库 Embedding 返回数据异常。")
    return embeddings


def index_document(document: KnowledgeDocument, *, force: bool = False) -> int:
    """Embed a document atomically, preserving prior indexed chunks on API failure."""

    document.index_status = KnowledgeDocument.IndexStatus.PROCESSING
    document.index_error = ""
    document.save(update_fields=["index_status", "index_error", "updated_at"])
    chunks = split_knowledge_content(document.content)
    if not chunks:
        document.index_status = KnowledgeDocument.IndexStatus.FAILED
        document.index_error = "知识文档没有可索引的内容。"
        document.save(update_fields=["index_status", "index_error", "updated_at"])
        raise KnowledgeBaseError(f"知识文档“{document.title}”没有可索引的内容。")
    hashes = [_hash_content(chunk) for chunk in chunks]
    existing = list(document.chunks.order_by("sequence").values_list("content_hash", "embedding"))
    if (
        not force
        and len(existing) == len(hashes)
        and [item[0] for item in existing] == hashes
        and all(item[1] is not None for item in existing)
    ):
        if settings.AFTER_SALES_VECTOR_BACKEND.lower() == "milvus":
            try:
                existing_chunks = list(document.chunks.order_by("sequence"))
                upsert_document_vectors(
                    document,
                    existing_chunks,
                    [list(chunk.embedding) for chunk in existing_chunks],
                )
            except MilvusUnavailable as exc:
                if not settings.AFTER_SALES_ALLOW_POSTGRES_FALLBACK:
                    document.index_status = KnowledgeDocument.IndexStatus.FAILED
                    document.index_error = str(exc)[:500]
                    document.save(update_fields=["index_status", "index_error", "updated_at"])
                    raise KnowledgeBaseError(str(exc)) from exc
                document.index_error = "Milvus 暂不可用，当前保留 PostgreSQL 备用索引。"
        document.index_status = KnowledgeDocument.IndexStatus.READY
        document.chunk_count = len(existing)
        document.indexed_at = timezone.now()
        document.save(
            update_fields=["index_status", "index_error", "chunk_count", "indexed_at", "updated_at"]
        )
        return 0

    try:
        embeddings = embed_texts(chunks)
        chunk_objects = []
        for index, chunk in enumerate(chunks):
            chunk_object = KnowledgeChunk(
                document=document,
                sequence=index,
                content=chunk,
                content_hash=hashes[index],
                embedding=embeddings[index],
            )
            chunk_object.vector_id = str(chunk_object.id)
            chunk_objects.append(chunk_object)
        with transaction.atomic():
            document.chunks.all().delete()
            created_chunks = KnowledgeChunk.objects.bulk_create(chunk_objects)
        if settings.AFTER_SALES_VECTOR_BACKEND.lower() == "milvus":
            try:
                upsert_document_vectors(document, created_chunks, embeddings)
            except MilvusUnavailable as exc:
                if not settings.AFTER_SALES_ALLOW_POSTGRES_FALLBACK:
                    raise KnowledgeBaseError(str(exc)) from exc
                logger.warning("Milvus unavailable while indexing %s; PostgreSQL fallback kept", document.id)
                document.index_error = "Milvus 暂不可用，当前保留 PostgreSQL 备用索引。"
        document.index_status = KnowledgeDocument.IndexStatus.READY
        document.chunk_count = len(created_chunks)
        document.indexed_at = timezone.now()
        document.save(
            update_fields=[
                "index_status",
                "index_error",
                "chunk_count",
                "indexed_at",
                "updated_at",
            ]
        )
    except Exception as exc:
        document.index_status = KnowledgeDocument.IndexStatus.FAILED
        document.index_error = str(exc)[:500]
        document.save(update_fields=["index_status", "index_error", "updated_at"])
        if isinstance(exc, KnowledgeBaseError):
            raise
        raise KnowledgeBaseError("知识文档索引失败，请检查 Embedding 服务或向量数据库。") from exc
    return len(chunks)


def upsert_seed_documents() -> tuple[list[KnowledgeDocument], int]:
    """Create or update the checked-in starter knowledge without duplicating documents."""

    documents = []
    created = 0
    for seed in KNOWLEDGE_DOCUMENTS:
        document, was_created = KnowledgeDocument.objects.update_or_create(
            slug=seed["slug"],
            defaults={**seed, "is_published": True},
        )
        documents.append(document)
        created += int(was_created)
    return documents, created


def bootstrap_seed_knowledge(*, force: bool = False) -> dict[str, int]:
    """Upsert starter documents and ensure every one has a current vector index."""

    documents, documents_created = upsert_seed_documents()
    chunks_indexed = sum(index_document(document, force=force) for document in documents)
    return {
        "documents": len(documents),
        "documents_created": documents_created,
        "chunks_indexed": chunks_indexed,
    }


def _scope_keys(*, product_id: str | None, category_id: str | None) -> list[str]:
    keys = ["GLOBAL"]
    if product_id:
        keys.append(f"PRODUCT:{product_id}")
        product_category_id = (
            Product.objects.filter(id=product_id).values_list("category_id", flat=True).first()
        )
        if product_category_id:
            keys.append(f"CATEGORY:{product_category_id}")
    if category_id:
        keys.append(f"CATEGORY:{category_id}")
    return list(dict.fromkeys(keys))


def _scope_priority(scope_key: str, *, product_id: str | None, category_id: str | None) -> int:
    """Prefer the most specific applicable rule over a global rule."""

    if product_id and scope_key == f"PRODUCT:{product_id}":
        return 2
    if (product_id or category_id) and scope_key.startswith("CATEGORY:"):
        return 1
    return 0


def _search_postgres(
    query_embedding: list[float], *, limit: int, product_id: str | None, category_id: str | None
) -> list[dict[str, Any]]:
    documents = KnowledgeDocument.objects.filter(
        is_published=True, index_status=KnowledgeDocument.IndexStatus.READY
    )
    scope_filter = Q(product__isnull=True, product_category__isnull=True)
    category_scope_ids: list[str] = []
    if product_id:
        category_id_for_product = (
            Product.objects.filter(id=product_id).values_list("category_id", flat=True).first()
        )
        scope_filter |= Q(product_id=product_id)
        if category_id_for_product:
            scope_filter |= Q(product_category_id=category_id_for_product)
            category_scope_ids.append(str(category_id_for_product))
    if category_id:
        scope_filter |= Q(product_category_id=category_id)
        category_scope_ids.append(str(category_id))
    priority_conditions = []
    if product_id:
        priority_conditions.append(When(product_id=product_id, then=2))
    if category_scope_ids:
        priority_conditions.append(When(product_category_id__in=category_scope_ids, then=1))
    scope_priority = Case(
        *priority_conditions,
        default=0,
        output_field=IntegerField(),
    )
    candidates = (
        KnowledgeChunk.objects.filter(document__in=documents, embedding__isnull=False)
        .filter(scope_filter)
        .select_related("document")
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .annotate(scope_priority=scope_priority)
        .filter(distance__lte=settings.AFTER_SALES_RAG_MAX_COSINE_DISTANCE)
        .order_by("-scope_priority", "distance")[: max(1, min(limit, MAX_RESULTS))]
    )
    return [
        {
            "document_id": str(chunk.document_id),
            "chunk_id": str(chunk.id),
            "title": chunk.document.title,
            "source_label": chunk.document.source_label,
            "source_type": chunk.document.source_type,
            "source_url": chunk.document.source_url,
            "category": chunk.document.category,
            "excerpt": chunk.content[:700],
            "similarity": round(max(0.0, 1 - float(chunk.distance)), 3),
            "sequence": chunk.sequence,
        }
        for chunk in candidates
    ]


def search_after_sales_knowledge(
    query: str,
    *,
    limit: int = DEFAULT_RESULTS,
    product_id: str | None = None,
    category_id: str | None = None,
) -> KnowledgeSearchResult:
    """Return only sufficiently similar trusted document chunks, otherwise require humans."""

    normalized_query = _embedding_text(query)
    if len(normalized_query) < 2:
        raise KnowledgeBaseError("知识库检索问题过短。")
    if not KnowledgeChunk.objects.filter(
        document__is_published=True,
        document__index_status=KnowledgeDocument.IndexStatus.READY,
        embedding__isnull=False,
    ).exists():
        return KnowledgeSearchResult(
            matches=[],
            requires_human_escalation=True,
            message="知识库尚未完成索引，无法提供可靠依据。",
        )

    query_embedding = embed_texts([normalized_query])[0]
    matches: list[dict[str, Any]] = []
    if settings.AFTER_SALES_VECTOR_BACKEND.lower() == "milvus":
        try:
            milvus_hits = search_vectors(
                query_embedding,
                scope_keys=_scope_keys(product_id=product_id, category_id=category_id),
                limit=max(1, min(limit * 4, 20)),
            )
            min_similarity = 1 - settings.AFTER_SALES_RAG_MAX_COSINE_DISTANCE
            chunk_ids = [
                hit["chunk_id"] for hit in milvus_hits if hit["similarity"] >= min_similarity
            ]
            chunk_map = {
                str(chunk.id): chunk
                for chunk in KnowledgeChunk.objects.filter(
                    id__in=chunk_ids,
                    document__is_published=True,
                    index_status=KnowledgeDocument.IndexStatus.READY,
                ).select_related("document")
            }
            best_hits: dict[str, dict[str, Any]] = {}
            for hit in milvus_hits:
                if hit["similarity"] < min_similarity:
                    continue
                current = best_hits.get(hit["chunk_id"])
                if current is None or (
                    _scope_priority(hit.get("scope_key", "GLOBAL"), product_id=product_id, category_id=category_id),
                    hit["similarity"],
                ) > (
                    _scope_priority(current.get("scope_key", "GLOBAL"), product_id=product_id, category_id=category_id),
                    current["similarity"],
                ):
                    best_hits[hit["chunk_id"]] = hit
            ordered_hits = sorted(
                best_hits.values(),
                key=lambda hit: (
                    -_scope_priority(
                        hit.get("scope_key", "GLOBAL"), product_id=product_id, category_id=category_id
                    ),
                    -hit["similarity"],
                ),
            )
            seen: set[str] = set()
            for hit in ordered_hits:
                chunk = chunk_map.get(hit["chunk_id"])
                if not chunk or hit["chunk_id"] in seen:
                    continue
                seen.add(hit["chunk_id"])
                matches.append(
                    {
                        "document_id": str(chunk.document_id),
                        "chunk_id": str(chunk.id),
                        "title": chunk.document.title,
                        "source_label": chunk.document.source_label,
                        "source_type": chunk.document.source_type,
                        "source_url": chunk.document.source_url,
                        "category": chunk.document.category,
                        "excerpt": chunk.content[:700],
                        "similarity": hit["similarity"],
                        "sequence": chunk.sequence,
                    }
                )
                if len(matches) >= limit:
                    break
        except MilvusUnavailable:
            if not settings.AFTER_SALES_ALLOW_POSTGRES_FALLBACK:
                raise KnowledgeBaseError("Milvus 检索暂不可用。")
            logger.warning("Milvus unavailable during search; using PostgreSQL fallback")
    if not matches:
        matches = _search_postgres(
            query_embedding, limit=limit, product_id=product_id, category_id=category_id
        )
    if not matches:
        return KnowledgeSearchResult(
            matches=[],
            requires_human_escalation=True,
            message="未检索到相似度足够的售后知识，必须转人工处理。",
        )
    return KnowledgeSearchResult(
        matches=matches,
        requires_human_escalation=False,
        message="已检索到可信售后知识，可据此回答并引用来源。",
    )
