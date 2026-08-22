from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="NetworkDesign",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("site", models.CharField(default="", max_length=100)),
                ("scenario", models.CharField(max_length=50)),
                ("vendor", models.CharField(max_length=50)),
                ("hld", models.JSONField(default=dict)),
                ("lld", models.JSONField(default=dict)),
                ("config_diff", models.TextField(default="")),
                ("rollback_config", models.TextField(default="")),
                ("lint_passed", models.BooleanField(default=False)),
                ("created_by", models.CharField(default="ai", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "网络设计方案", "verbose_name_plural": "网络设计方案", "ordering": ["-created_at"]},
        ),
    ]
