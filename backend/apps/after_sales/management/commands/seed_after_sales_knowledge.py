"""Seed and embed the trusted after-sales knowledge base."""

from django.core.management.base import BaseCommand, CommandError

from apps.after_sales.knowledge import KnowledgeBaseError, bootstrap_seed_knowledge


class Command(BaseCommand):
    help = "导入并向量化内置的中文售后知识库。需要配置 OPENAI_API_KEY。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="即使文档内容未变化，也重新生成全部 Embedding。",
        )

    def handle(self, *args, **options):
        try:
            result = bootstrap_seed_knowledge(force=options["force"])
        except KnowledgeBaseError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "售后知识库已就绪："
                f"{result['documents']} 篇文档，新增 {result['documents_created']} 篇，"
                f"本次写入 {result['chunks_indexed']} 个向量切片。"
            )
        )
