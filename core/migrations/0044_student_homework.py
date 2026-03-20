# Generated manually for StudentHomework

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0043_student_teacher_notes"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentHomework",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pendente"), ("done", "Concluído")], default="pending", max_length=10)),
                ("student_response", models.TextField(blank=True, help_text="Resposta/entrega em texto (opcional)")),
                ("teacher_feedback", models.TextField(blank=True, help_text="Feedback do professor (opcional)")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_by", models.ForeignKey(help_text="Professor que atribuiu o homework", on_delete=django.db.models.deletion.CASCADE, related_name="assigned_homeworks", to="auth.user")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="homeworks", to="core.student")),
            ],
            options={
                "verbose_name": "Homework do Aluno",
                "verbose_name_plural": "Homeworks dos Alunos",
                "ordering": ["-created_at"],
            },
        ),
    ]

