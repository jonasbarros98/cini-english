from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0048_studenthomeworkmessageread"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentMaterial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, help_text="Título exibido para o aluno")),
                ("material_type", models.CharField(choices=[("file", "Arquivo"), ("link", "Link")], default="file", max_length=10)),
                ("file", models.FileField(blank=True, null=True, upload_to="student_materials/%Y/%m/")),
                ("external_url", models.URLField(blank=True, default="")),
                ("file_size", models.PositiveIntegerField(default=0)),
                ("material_date", models.DateField(help_text="Data de referência para organização dos materiais")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="materials", to="core.student")),
                ("user", models.ForeignKey(help_text="Professor que criou o material", on_delete=django.db.models.deletion.CASCADE, related_name="student_materials", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Material do Aluno",
                "verbose_name_plural": "Materiais dos Alunos",
                "ordering": ["-material_date", "-created_at"],
            },
        ),
    ]
