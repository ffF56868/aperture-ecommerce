"""Layered memory system for customer personalization.

This module implements three-tier memory:
- WORKING: Current session context (24h TTL)
- EPISODIC: Session/case summaries (60d TTL)
- LONG_TERM: User preferences (persistent)

Features:
- Vector search with time-decay ranking
- Conflict detection with version chain
- Async extraction via Celery
"""

import json
import logging
import math
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone
from pgvector.django import CosineDistance

from .knowledge import KnowledgeBaseError, embed_texts
from .models import AgentConversation, AgentMessage, CustomerMemory

logger = logging.getLogger(__name__)

# Half-life in days for each memory layer
HALF_LIFE_DAYS = {
    CustomerMemory.MemoryLayer.WORKING: 1,
    CustomerMemory.MemoryLayer.EPISODIC: 30,
    CustomerMemory.MemoryLayer.LONG_TERM: 365,
}

# Intent keywords for boosting relevant memories
INTENT_KEYWORDS = {
    "REFUND": ["退款", "退钱", "退回"],
    "RETURN_REFUND": ["退货", "退回", "换货"],
    "QUALITY_ISSUE": ["质量", "破损", "瑕疵", "错发"],
    "DELIVERY_ISSUE": ["物流", "发货", "快递", "配送"],
    "CANCEL_ORDER": ["取消", "退单"],
    "ORDER_QUERY": ["订单", "购买", "下单", "物流"],
    "CASE_QUERY": ["工单", "审核", "进度"],
    "KNOWLEDGE_QUERY": ["尺码", "面料", "材质", "洗涤", "保养"],
    "HUMAN_SERVICE": ["人工", "客服"],
}


class MemoryError(RuntimeError):
    """A safe failure when memory operations cannot be completed."""


def compute_decay_score(created_at, half_life_days: float) -> float:
    """Compute time-decay factor based on memory age.

    Uses exponential decay: 0.5 ^ (age_days / half_life)
    """
    age_days = (timezone.now() - created_at).total_seconds() / 86400
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def _intent_boost(memory: CustomerMemory, intent: str) -> float:
    """Return a boost multiplier if memory is relevant to current intent."""
    if not intent or intent not in INTENT_KEYWORDS:
        return 1.0

    keywords = INTENT_KEYWORDS[intent]
    key_text = memory.key.lower()
    value_text = json.dumps(memory.value, ensure_ascii=False).lower()

    for keyword in keywords:
        if keyword in key_text or keyword in value_text:
            return 1.5
    return 1.0


def search_memories(
    user,
    query_embedding: list[float],
    intent: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Search memories with vector similarity + time-decay ranking.

    Returns top-K memories with score breakdown.
    """
    now = timezone.now()

    # Filter: active, not expired
    candidates = CustomerMemory.objects.filter(
        user=user,
        is_active=True,
        embedding__isnull=False,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )

    # Vector similarity search
    candidates = candidates.annotate(
        distance=CosineDistance("embedding", query_embedding)
    )

    # Filter by max distance threshold (same as knowledge RAG)
    max_distance = getattr(settings, "AFTER_SALES_RAG_MAX_COSINE_DISTANCE", 0.55)
    candidates = candidates.filter(distance__lte=max_distance)

    # Fetch candidates (limit higher to allow for scoring)
    memories = list(candidates.order_by("distance")[: limit * 3])

    # Compute composite score for each
    scored = []
    for memory in memories:
        similarity = max(0.0, 1 - float(memory.distance))
        half_life = HALF_LIFE_DAYS.get(memory.memory_layer, 30)
        decay = compute_decay_score(memory.created_at, half_life)
        access_boost = 1 + math.log(1 + memory.access_count) * 0.1
        intent_mult = _intent_boost(memory, intent)

        final_score = similarity * decay * access_boost * intent_mult

        scored.append({
            "memory": memory,
            "score": final_score,
            "similarity": similarity,
            "decay": decay,
            "access_boost": access_boost,
            "intent_boost": intent_mult,
        })

    # Sort by final score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Update access stats for top-K
    top_k = scored[:limit]
    if top_k:
        memory_ids = [item["memory"].id for item in top_k]
        CustomerMemory.objects.filter(id__in=memory_ids).update(
            access_count=F("access_count") + 1,
            last_accessed_at=now,
        )

    return top_k


def upsert_preference(
    user,
    key: str,
    value: dict[str, Any],
    source_conversation: AgentConversation | None = None,
) -> CustomerMemory:
    """Create or update a LONG_TERM preference memory with conflict detection.

    If a preference with the same key exists and value differs:
    - Mark old memory as inactive
    - Create new memory with version+1 and supersedes link
    """
    value_json = json.dumps(value, ensure_ascii=False, sort_keys=True)

    # Check for existing preference
    existing = CustomerMemory.objects.filter(
        user=user,
        memory_type=CustomerMemory.MemoryType.PREFERENCE,
        memory_layer=CustomerMemory.MemoryLayer.LONG_TERM,
        key=key,
        is_active=True,
    ).first()

    if existing:
        existing_value = json.dumps(existing.value, ensure_ascii=False, sort_keys=True)
        if existing_value == value_json:
            # Same value, just update timestamp
            existing.save(update_fields=["updated_at"])
            return existing

        # Conflict detected: deactivate old, create new
        existing.is_active = False
        existing.save(update_fields=["is_active", "updated_at"])

        new_version = existing.version + 1
        supersedes_id = existing.id
    else:
        new_version = 1
        supersedes_id = None

    # Generate embedding
    embedding_text = f"{key}: {value_json}"
    try:
        embeddings = embed_texts([embedding_text])
        embedding = embeddings[0] if embeddings else None
    except KnowledgeBaseError:
        logger.warning("Failed to generate embedding for preference %s", key)
        embedding = None

    # Create new memory
    memory = CustomerMemory.objects.create(
        user=user,
        source_conversation=source_conversation,
        memory_type=CustomerMemory.MemoryType.PREFERENCE,
        memory_layer=CustomerMemory.MemoryLayer.LONG_TERM,
        key=key,
        value=value,
        is_active=True,
        embedding=embedding,
        expires_at=None,  # LONG_TERM has no expiration
        version=new_version,
        supersedes_id=supersedes_id,
    )

    return memory


def create_episodic_memory(
    user,
    summary: str,
    source_conversation: AgentConversation | None = None,
) -> CustomerMemory:
    """Create an EPISODIC memory with 60-day expiration."""
    # Generate embedding
    try:
        embeddings = embed_texts([summary])
        embedding = embeddings[0] if embeddings else None
    except KnowledgeBaseError:
        logger.warning("Failed to generate embedding for episodic memory")
        embedding = None

    # Create memory with 60-day expiration
    expires_at = timezone.now() + timedelta(days=60)

    memory = CustomerMemory.objects.create(
        user=user,
        source_conversation=source_conversation,
        memory_type=CustomerMemory.MemoryType.CONVERSATION_SUMMARY,
        memory_layer=CustomerMemory.MemoryLayer.EPISODIC,
        key=f"summary_{source_conversation.id if source_conversation else 'unknown'}",
        value={"summary": summary},
        is_active=True,
        embedding=embedding,
        expires_at=expires_at,
    )

    return memory


def extract_memories_from_conversation(conversation_id: str) -> dict[str, int]:
    """Extract preferences and summary from a conversation using LLM.

    Called by Celery task after conversation ends.
    Returns counts of extracted memories.
    """
    from .openai_client import get_openai_client, get_openai_model

    try:
        conversation = AgentConversation.objects.select_related("user").get(id=conversation_id)
    except AgentConversation.DoesNotExist:
        logger.warning("Conversation %s not found for memory extraction", conversation_id)
        return {"preferences": 0, "summaries": 0}

    # Get recent messages (last 6)
    messages = list(
        conversation.messages.filter(
            role__in=(AgentMessage.Role.USER, AgentMessage.Role.ASSISTANT)
        ).order_by("-created_at")[:6]
    )
    messages.reverse()  # chronological order

    if not messages:
        return {"preferences": 0, "summaries": 0}

    # Build conversation text for LLM
    conversation_text = []
    for msg in messages:
        role = "用户" if msg.role == AgentMessage.Role.USER else "助手"
        conversation_text.append(f"{role}：{msg.content[:500]}")
    conversation_text = "\n".join(conversation_text)

    # LLM extraction prompt
    extraction_prompt = f"""请从以下对话中提取：
1. 用户偏好（PREFERENCE）：用户表达的习惯、要求、喜好，如"我喜欢纯棉的"、"不要发顺丰"
2. 会话摘要（SUMMARY）：本次对话的核心事实，如"用户订单 X 已退款"

对话内容：
{conversation_text}

请以 JSON 格式返回，结构如下：
{{
  "preferences": [
    {{"key": "偏好键", "value": {{"description": "偏好描述"}}}}
  ],
  "summary": "本次对话的核心摘要（一句话）"
}}

如果没有可提取的偏好，preferences 返回空数组。
如果没有可提取的摘要，summary 返回空字符串。
只返回 JSON，不要其他内容。"""

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=get_openai_model(),
            messages=[
                {"role": "system", "content": "你是一个信息提取助手，只返回 JSON 格式的结果。"},
                {"role": "user", "content": extraction_prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        result_text = response.choices[0].message.content.strip()
        # Parse JSON
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result = json.loads(result_text)
    except Exception as exc:
        logger.warning("Failed to extract memories from conversation %s: %s", conversation_id, exc)
        return {"preferences": 0, "summaries": 0}

    # Write extracted memories
    preferences_count = 0
    summaries_count = 0

    # Extract preferences
    for pref in result.get("preferences", []):
        key = pref.get("key", "").strip()
        value = pref.get("value", {})
        if key and value:
            try:
                upsert_preference(
                    user=conversation.user,
                    key=key,
                    value=value,
                    source_conversation=conversation,
                )
                preferences_count += 1
            except Exception as exc:
                logger.warning("Failed to upsert preference %s: %s", key, exc)

    # Extract summary
    summary = result.get("summary", "").strip()
    if summary:
        try:
            create_episodic_memory(
                user=conversation.user,
                summary=summary,
                source_conversation=conversation,
            )
            summaries_count += 1
        except Exception as exc:
            logger.warning("Failed to create episodic memory: %s", exc)

    logger.info(
        "Extracted %d preferences and %d summaries from conversation %s",
        preferences_count,
        summaries_count,
        conversation_id,
    )

    return {"preferences": preferences_count, "summaries": summaries_count}
