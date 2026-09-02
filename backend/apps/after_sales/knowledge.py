"""Trusted-document embedding, indexing and vector retrieval for the after-sales Agent."""

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from pgvector.django import CosineDistance

from .knowledge_seed import KNOWLEDGE_DOCUMENTS
from .models import KnowledgeChunk, KnowledgeDocument
from .openai_client import OpenAIConfigurationError, get_openai_client

CHUNK_SIZE = 520
CHUNK_OVERLAP = 80
MAX_RESULTS = 3


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
        response = get_openai_client().embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=[_embedding_text(text) for text in texts],
            dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
        )
    except OpenAIConfigurationError as exc:
        raise KnowledgeBaseError("未配置知识库 Embedding 服务。") from exc
    except Exception as exc:
        raise KnowledgeBaseError("知识库 Embedding 服务暂时不可用。") from exc

    ordered = sorted(response.data, key=lambda item: item.index)
    embeddings = [list(item.embedding) for item in ordered]
    if len(embeddings) != len(texts) or any(
        len(embedding) != settings.OPENAI_EMBEDDING_DIMENSIONS for embedding in embeddings
    ):
        raise KnowledgeBaseError("知识库 Embedding 返回数据异常。")
    return embeddings


def index_document(document: KnowledgeDocument, *, force: bool = False) -> int:
    """Embed a document atomically, preserving prior indexed chunks on API failure."""

    chunks = split_knowledge_content(document.content)
    if not chunks:
        raise KnowledgeBaseError(f"知识文档“{document.title}”没有可索引的内容。")
    hashes = [_hash_content(chunk) for chunk in chunks]
    existing = list(document.chunks.order_by("sequence").values_list("content_hash", "embedding"))
    if (
        not force
        and len(existing) == len(hashes)
        and [item[0] for item in existing] == hashes
        and all(item[1] is not None for item in existing)
    ):
        return 0

    embeddings = embed_texts(chunks)
    with transaction.atomic():
        document.chunks.all().delete()
        KnowledgeChunk.objects.bulk_create(
            [
                KnowledgeChunk(
                    document=document,
                    sequence=index,
                    content=chunk,
                    content_hash=hashes[index],
                    embedding=embeddings[index],
                )
                for index, chunk in enumerate(chunks)
            ]
        )
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


def search_after_sales_knowledge(query: str, *, limit: int = MAX_RESULTS) -> KnowledgeSearchResult:
    """Return only sufficiently similar trusted document chunks, otherwise require humans."""

    normalized_query = _embedding_text(query)
    if len(normalized_query) < 2:
        raise KnowledgeBaseError("知识库检索问题过短。")
    if not KnowledgeChunk.objects.filter(
        document__is_published=True, embedding__isnull=False
    ).exists():
        return KnowledgeSearchResult(
            matches=[],
            requires_human_escalation=True,
            message="知识库尚未完成索引，无法提供可靠依据。",
        )

    query_embedding = embed_texts([normalized_query])[0]
    threshold = settings.AFTER_SALES_RAG_MAX_COSINE_DISTANCE
    candidates = (
        KnowledgeChunk.objects.filter(document__is_published=True, embedding__isnull=False)
        .select_related("document")
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .filter(distance__lte=threshold)
        .order_by("distance")[: max(1, min(limit, MAX_RESULTS))]
    )
    matches = [
        {
            "document_id": str(chunk.document_id),
            "title": chunk.document.title,
            "source_label": chunk.document.source_label,
            "category": chunk.document.category,
            "excerpt": chunk.content[:700],
            "similarity": round(max(0.0, 1 - float(chunk.distance)), 3),
        }
        for chunk in candidates
    ]
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
