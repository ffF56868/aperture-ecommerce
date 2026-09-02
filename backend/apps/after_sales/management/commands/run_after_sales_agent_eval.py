"""Run the deterministic after-sales Agent regression evaluation."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.after_sales.evaluation import AfterSalesAgentEvaluator


class Command(BaseCommand):
    help = "运行 20 条售后 Agent 回放评测并生成 Markdown/JSON 报告。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="after-sales-agent-eval-report.md",
            help="Markdown 报告路径，默认相对项目根目录。",
        )
        parser.add_argument(
            "--json-output",
            default="after-sales-agent-eval-report.json",
            help="JSON 报告路径，默认相对项目根目录。",
        )

    @staticmethod
    def _resolve_output_path(value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        mounted_docs = Path("/project_docs")
        if mounted_docs.is_dir():
            return mounted_docs / path
        return Path(settings.BASE_DIR) / "docs" / path

    def handle(self, *args, **options):
        report = AfterSalesAgentEvaluator().run()
        markdown_path = self._resolve_output_path(options["output"])
        json_path = self._resolve_output_path(options["json_output"])
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(report.to_markdown(), encoding="utf-8")
        json_path.write_text(
            json.dumps(report.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        summary = report.as_dict()["summary"]
        self.stdout.write(
            self.style.SUCCESS(
                f"售后 Agent Eval 已完成：{summary['passed']}/{summary['total']} 通过。\n"
                f"Markdown：{markdown_path}\nJSON：{json_path}"
            )
        )
        if summary["failed"]:
            raise CommandError(f"售后 Agent Eval 有 {summary['failed']} 条失败，请查看报告。")
