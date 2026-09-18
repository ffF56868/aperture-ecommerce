"""Add layered memory fields to CustomerMemory."""

import django.db.models.deletion
from django.db import migrations, models
from pgvector.django import HnswIndex, VectorField


class Migration(migrations.Migration):

    dependencies = [
        ("after_sales", "0010_alter_knowledgedocument_index_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="customermemory",
            name="memory_layer",
            field=models.CharField(
                choices=[
                    ("WORKING", "工作记忆"),
                    ("EPISODIC", "情景记忆"),
                    ("LONG_TERM", "长期记忆"),
                ],
                default="EPISODIC",
                max_length=16,
                verbose_name="记忆层级",
            ),
        ),
        migrations.AddField(
            model_name="customermemory",
            name="embedding",
            field=VectorField(
                blank=True,
                dimensions=1536,
                null=True,
                verbose_name="向量",
            ),
        ),
        migrations.AddField(
            model_name="customermemory",
            name="expires_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="过期时间",
            ),
        ),
        migrations.AddField(
            model_name="customermemory",
            name="access_count",
            field=models.PositiveIntegerField(default=0, verbose_name="访问次数"),
        ),
        migrations.AddField(
            model_name="customermemory",
            name="last_accessed_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="最后访问时间",
            ),
        ),
        migrations.AddField(
            model_name="customermemory",
            name="version",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="版本号"),
        ),
        migrations.AddField(
            model_name="customermemory",
            name="supersedes",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="superseded_by",
                to="after_sales.customermemory",
                verbose_name="替代记忆",
            ),
        ),
        migrations.AddIndex(
            model_name="customermemory",
            index=models.Index(
                fields=["user", "memory_layer", "is_active", "expires_at"],
                name="after_sales_user_id_d4a159_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="customermemory",
            index=HnswIndex(
                ef_construction=64,
                fields=["embedding"],
                m=16,
                name="customer_memory_emb_hnsw",
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
