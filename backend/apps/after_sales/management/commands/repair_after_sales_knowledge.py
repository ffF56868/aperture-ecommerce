"""Repair PostgreSQL/Milvus after-sales knowledge index consistency."""

from django.core.management.base import BaseCommand, CommandError

from apps.after_sales.knowledge import KnowledgeBaseError, index_document
from apps.after_sales.models import KnowledgeDocument
from apps.after_sales.vector_store import (
    MilvusUnavailable,
    _scopes,
    delete_orphaned_document_vectors,
    document_vector_count,
)


class Command(BaseCommand):
    help = "校验并修复 PostgreSQL 与 Milvus 中的售后知识索引。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--document-id",
            help="只修复指定文档；不传则修复全部文档。",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="强制重新生成 Embedding；默认复用 PostgreSQL 中已有向量。",
        )

    def handle(self, *args, **options):
        queryset = KnowledgeDocument.objects.all().order_by("slug")
        document_id = options.get("document_id")
        if document_id:
            queryset = queryset.filter(id=document_id)
            if not queryset.exists():
                raise CommandError("指定的知识文档不存在。")

        documents = list(queryset)
        valid_document_ids = {
            str(document_id) for document_id in KnowledgeDocument.objects.values_list("id", flat=True)
        }
        repaired = 0
        failed = 0

        for document in documents:
            try:
                index_document(document, force=options["force"])
                document.refresh_from_db()
                expected = document.chunks.count() * len(_scopes(document))
                actual = document_vector_count(str(document.id))
                if document.chunk_count != document.chunks.count() or actual != expected:
                    raise MilvusUnavailable(
                        f"文档 {document.slug} 校验失败：数据库切片 {document.chunks.count()} 个，"
                        f"Milvus 向量 {actual} 条，期望 {expected} 条。"
                    )
                repaired += 1
                self.stdout.write(f"已同步：{document.title}（{actual} 条 Milvus 向量）")
            except (KnowledgeBaseError, MilvusUnavailable) as exc:
                failed += 1
                KnowledgeDocument.objects.filter(id=document.id).update(
                    index_status=KnowledgeDocument.IndexStatus.FAILED,
                    index_error=str(exc)[:500],
                )
                self.stderr.write(self.style.ERROR(f"同步失败：{document.title}：{exc}"))

        try:
            orphaned_documents = delete_orphaned_document_vectors(valid_document_ids)
        except MilvusUnavailable as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"知识库同步完成：成功 {repaired} 篇，失败 {failed} 篇，"
                f"清理 {orphaned_documents} 个孤儿文档向量。"
            )
        )
        if failed:
            raise CommandError("部分知识文档同步失败，请查看上面的错误并重试。")
