"""Clean up expired customer memories."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.after_sales.models import CustomerMemory


class Command(BaseCommand):
    help = "清理已过期的客户记忆（EPISODIC 和 WORKING 层）。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅显示将要清理的记忆数量，不实际执行清理。",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        # Find expired memories
        expired_memories = CustomerMemory.objects.filter(
            is_active=True,
            expires_at__lt=now,
        )

        count = expired_memories.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("没有发现已过期的记忆。"))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"发现 {count} 条已过期的记忆（dry-run 模式，未实际清理）。")
            )
            # Show breakdown by layer
            for layer in [CustomerMemory.MemoryLayer.WORKING, CustomerMemory.MemoryLayer.EPISODIC]:
                layer_count = expired_memories.filter(memory_layer=layer).count()
                if layer_count > 0:
                    self.stdout.write(f"  - {layer}: {layer_count} 条")
            return

        # Deactivate expired memories
        updated_count = expired_memories.update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(f"成功清理 {updated_count} 条已过期的记忆。")
        )

        # Show breakdown by layer
        for layer in [CustomerMemory.MemoryLayer.WORKING, CustomerMemory.MemoryLayer.EPISODIC]:
            layer_count = expired_memories.filter(memory_layer=layer).count()
            if layer_count > 0:
                self.stdout.write(f"  - {layer}: {layer_count} 条")
