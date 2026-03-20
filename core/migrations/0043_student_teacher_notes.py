# Generated manually for Student.teacher_notes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_add_student_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='teacher_notes',
            field=models.TextField(
                blank=True,
                help_text='Observações do professor sobre o aluno (visível na ficha do aluno)',
            ),
        ),
    ]
