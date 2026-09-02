from unittest.mock import patch

from django.test import TestCase

from apps.after_sales.knowledge import KnowledgeSearchResult, split_knowledge_content, upsert_seed_documents
from apps.after_sales.models import KnowledgeChunk


class AfterSalesKnowledgeTests(TestCase):
    def test_seed_documents_are_repeatable(self):
        documents, created = upsert_seed_documents()
        repeated_documents, repeated_created = upsert_seed_documents()

        self.assertEqual(len(documents), 12)
        self.assertEqual(created, 12)
        self.assertEqual(len(repeated_documents), 12)
        self.assertEqual(repeated_created, 0)

    def test_split_knowledge_content_keeps_short_document_as_one_chunk(self):
        self.assertEqual(split_knowledge_content("尺码以商品详情页为准。"), ["尺码以商品详情页为准。"])

    @patch("apps.after_sales.knowledge.embed_texts", return_value=[[0.1] * 1536])
    def test_indexing_reuses_current_embeddings_when_content_is_unchanged(self, mock_embed):
        document = upsert_seed_documents()[0][0]
        from apps.after_sales.knowledge import index_document

        self.assertEqual(index_document(document), 1)
        self.assertEqual(KnowledgeChunk.objects.count(), 1)
        self.assertEqual(index_document(document), 0)
        self.assertEqual(mock_embed.call_count, 1)

    def test_search_result_contract_can_require_human_escalation(self):
        result = KnowledgeSearchResult(
            matches=[],
            requires_human_escalation=True,
            message="未命中。",
        )

        self.assertTrue(result.requires_human_escalation)
        self.assertEqual(result.matches, [])
