"""Tests for the layered memory system."""

import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from apps.after_sales.memory import (
    compute_decay_score,
    create_episodic_memory,
    extract_memories_from_conversation,
    search_memories,
    upsert_preference,
)
from apps.after_sales.models import AgentConversation, AgentMessage, CustomerMemory
from apps.authentication.models import User


class MemoryDecayTests(TestCase):
    """Test time-decay scoring for memories."""

    def test_compute_decay_score_recent_memory(self):
        """Recent memories should have high decay scores."""
        now = timezone.now()
        score = compute_decay_score(now, half_life_days=30)
        self.assertGreater(score, 0.9)

    def test_compute_decay_score_old_memory(self):
        """Old memories should have lower decay scores."""
        old_date = timezone.now() - timedelta(days=60)
        score = compute_decay_score(old_date, half_life_days=30)
        self.assertLess(score, 0.3)

    def test_compute_decay_score_zero_half_life(self):
        """Zero half-life should return 1.0 (no decay)."""
        score = compute_decay_score(timezone.now(), half_life_days=0)
        self.assertEqual(score, 1.0)


class PreferenceUpsertTests(TestCase):
    """Test preference upsertion with conflict detection."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="memory_test_user",
            phone_number="+8613800138000",
            password="testpass123",
        )
        self.conversation = AgentConversation.objects.create(user=self.user)

    @patch("apps.after_sales.memory.embed_texts")
    def test_upsert_preference_creates_new(self, mock_embed):
        """First upsert should create a new preference."""
        mock_embed.return_value = [[0.1] * 1536]

        memory = upsert_preference(
            user=self.user,
            key="preferred_material",
            value={"material": "cotton"},
            source_conversation=self.conversation,
        )

        self.assertEqual(memory.memory_type, CustomerMemory.MemoryType.PREFERENCE)
        self.assertEqual(memory.memory_layer, CustomerMemory.MemoryLayer.LONG_TERM)
        self.assertEqual(memory.key, "preferred_material")
        self.assertEqual(memory.version, 1)
        self.assertIsNone(memory.supersedes)
        self.assertTrue(memory.is_active)

    @patch("apps.after_sales.memory.embed_texts")
    def test_upsert_preference_same_value_no_change(self, mock_embed):
        """Upserting same value should not create new version."""
        mock_embed.return_value = [[0.1] * 1536]

        # Create initial preference
        memory1 = upsert_preference(
            user=self.user,
            key="preferred_material",
            value={"material": "cotton"},
        )

        # Upsert same value
        memory2 = upsert_preference(
            user=self.user,
            key="preferred_material",
            value={"material": "cotton"},
        )

        self.assertEqual(memory1.id, memory2.id)
        self.assertEqual(memory2.version, 1)

    @patch("apps.after_sales.memory.embed_texts")
    def test_upsert_preference_conflict_detection(self, mock_embed):
        """Changing preference value should create new version with supersedes link."""
        mock_embed.return_value = [[0.1] * 1536]

        # Create initial preference
        memory1 = upsert_preference(
            user=self.user,
            key="preferred_material",
            value={"material": "cotton"},
        )

        # Change preference
        memory2 = upsert_preference(
            user=self.user,
            key="preferred_material",
            value={"material": "silk"},
        )

        # Old memory should be deactivated
        memory1.refresh_from_db()
        self.assertFalse(memory1.is_active)

        # New memory should have version 2 and supersedes link
        self.assertEqual(memory2.version, 2)
        self.assertEqual(memory2.supersedes_id, memory1.id)
        self.assertTrue(memory2.is_active)


class EpisodicMemoryTests(TestCase):
    """Test episodic memory creation with TTL."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="episodic_test_user",
            phone_number="+8613800138001",
            password="testpass123",
        )
        self.conversation = AgentConversation.objects.create(user=self.user)

    @patch("apps.after_sales.memory.embed_texts")
    def test_create_episodic_memory_with_ttl(self, mock_embed):
        """Episodic memories should have 60-day TTL."""
        mock_embed.return_value = [[0.1] * 1536]

        memory = create_episodic_memory(
            user=self.user,
            summary="用户询问了退货流程",
            source_conversation=self.conversation,
        )

        self.assertEqual(memory.memory_type, CustomerMemory.MemoryType.CONVERSATION_SUMMARY)
        self.assertEqual(memory.memory_layer, CustomerMemory.MemoryLayer.EPISODIC)
        self.assertIsNotNone(memory.expires_at)

        # Should expire in approximately 60 days
        expected_expiry = timezone.now() + timedelta(days=60)
        time_diff = abs((memory.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 60)  # Within 1 minute


class MemorySearchTests(TestCase):
    """Test vector-based memory search with ranking."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="search_test_user",
            phone_number="+8613800138002",
            password="testpass123",
        )

    @patch("apps.after_sales.memory.embed_texts")
    def test_search_memories_vector_ranking(self, mock_embed):
        """Search should rank memories by vector similarity."""
        mock_embed.return_value = [[0.1] * 1536]

        # Create memories with different keys
        upsert_preference(self.user, "preferred_color", {"color": "blue"})
        upsert_preference(self.user, "preferred_size", {"size": "M"})

        # Search with query embedding
        query_embedding = [0.1] * 1536
        results = search_memories(
            user=self.user,
            query_embedding=query_embedding,
            intent="ORDER_QUERY",
            limit=3,
        )

        # Should return both memories
        self.assertEqual(len(results), 2)

        # Each result should have score breakdown
        for result in results:
            self.assertIn("memory", result)
            self.assertIn("score", result)
            self.assertIn("similarity", result)
            self.assertIn("decay", result)

    @patch("apps.after_sales.memory.embed_texts")
    def test_search_memories_intent_boost(self, mock_embed):
        """Memories matching current intent should get score boost."""
        mock_embed.return_value = [[0.1] * 1536]

        # Create memories
        upsert_preference(self.user, "refund_preference", {"method": "original"})
        upsert_preference(self.user, "shipping_preference", {"speed": "standard"})

        # Search with REFUND intent
        query_embedding = [0.1] * 1536
        results = search_memories(
            user=self.user,
            query_embedding=query_embedding,
            intent="REFUND",
            limit=3,
        )

        # refund_preference should rank higher due to intent boost
        if len(results) >= 2:
            self.assertEqual(results[0]["memory"].key, "refund_preference")


class MemoryExtractionTests(TestCase):
    """Test LLM-based memory extraction from conversations."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="extraction_test_user",
            phone_number="+8613800138003",
            password="testpass123",
        )
        self.conversation = AgentConversation.objects.create(user=self.user)

        # Add some messages
        AgentMessage.objects.create(
            conversation=self.conversation,
            role=AgentMessage.Role.USER,
            content="我喜欢纯棉的衣服",
        )
        AgentMessage.objects.create(
            conversation=self.conversation,
            role=AgentMessage.Role.ASSISTANT,
            content="好的，我记住了，您偏好纯棉材质。",
        )

    @patch("apps.after_sales.memory.embed_texts")
    @patch("apps.after_sales.memory.get_openai_client")
    def test_extract_memories_from_conversation(self, mock_client, mock_embed):
        """Should extract preferences and summary from conversation."""
        mock_embed.return_value = [[0.1] * 1536]

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "preferences": [
                {"key": "material_preference", "value": {"material": "cotton"}}
            ],
            "summary": "用户表达了偏好纯棉材质的需求",
        })
        mock_client.return_value.chat.completions.create.return_value = mock_response

        result = extract_memories_from_conversation(str(self.conversation.id))

        # Should extract 1 preference and 1 summary
        self.assertEqual(result["preferences"], 1)
        self.assertEqual(result["summaries"], 1)

        # Verify memories were created
        preference_count = CustomerMemory.objects.filter(
            user=self.user,
            memory_type=CustomerMemory.MemoryType.PREFERENCE,
        ).count()
        self.assertEqual(preference_count, 1)

        summary_count = CustomerMemory.objects.filter(
            user=self.user,
            memory_type=CustomerMemory.MemoryType.CONVERSATION_SUMMARY,
        ).count()
        self.assertEqual(summary_count, 1)


class ExpiredMemoryFilterTests(TestCase):
    """Test that expired memories are filtered from search results."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="expired_test_user",
            phone_number="+8613800138004",
            password="testpass123",
        )

    @patch("apps.after_sales.memory.embed_texts")
    def test_expired_memories_filtered(self, mock_embed):
        """Expired memories should not appear in search results."""
        mock_embed.return_value = [[0.1] * 1536]

        # Create an expired memory
        expired_memory = CustomerMemory.objects.create(
            user=self.user,
            memory_type=CustomerMemory.MemoryType.PREFERENCE,
            memory_layer=CustomerMemory.MemoryLayer.EPISODIC,
            key="old_preference",
            value={"old": "value"},
            embedding=[0.1] * 1536,
            expires_at=timezone.now() - timedelta(days=1),  # Expired yesterday
            is_active=True,
        )

        # Create an active memory
        active_memory = CustomerMemory.objects.create(
            user=self.user,
            memory_type=CustomerMemory.MemoryType.PREFERENCE,
            memory_layer=CustomerMemory.MemoryLayer.LONG_TERM,
            key="current_preference",
            value={"current": "value"},
            embedding=[0.1] * 1536,
            expires_at=None,  # No expiration
            is_active=True,
        )

        # Search
        query_embedding = [0.1] * 1536
        results = search_memories(
            user=self.user,
            query_embedding=query_embedding,
            intent="GENERAL",
            limit=3,
        )

        # Should only return active memory
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["memory"].id, active_memory.id)
