from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_homework_messages(apps, schema_editor):
    StudentHomework = apps.get_model("core", "StudentHomework")
    StudentHomeworkMessage = apps.get_model("core", "StudentHomeworkMessage")

    for hw in StudentHomework.objects.all().iterator():
        has_existing = StudentHomeworkMessage.objects.filter(homework_id=hw.id).exists()
        if has_existing:
            continue

        student_text = (hw.student_response or "").strip()
        teacher_text = (hw.teacher_feedback or "").strip()

        if student_text:
            StudentHomeworkMessage.objects.create(
                homework_id=hw.id,
                sender="student",
                message=student_text,
                created_by=None,
            )
        if teacher_text:
            StudentHomeworkMessage.objects.create(
                homework_id=hw.id,
                sender="teacher",
                message=teacher_text,
                created_by=hw.assigned_by,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0046_studentsharetoken"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentHomeworkMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender", models.CharField(choices=[("student", "Aluno"), ("teacher", "Professor")], max_length=10)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_homework_messages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "homework",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="core.studenthomework",
                    ),
                ),
            ],
            options={
                "verbose_name": "Mensagem da Tarefa do Aluno",
                "verbose_name_plural": "Mensagens das Tarefas dos Alunos",
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.RunPython(backfill_homework_messages, migrations.RunPython.noop),
    ]
