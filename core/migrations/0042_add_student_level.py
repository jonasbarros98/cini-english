# Generated manually for Student.level (CEFR)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_alter_student_plan_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='level',
            field=models.CharField(
                blank=True,
                choices=[
                    ('A1', 'A1'),
                    ('A2', 'A2'),
                    ('B1', 'B1'),
                    ('B2', 'B2'),
                    ('C1', 'C1'),
                    ('C2', 'C2'),
                ],
                help_text='Nível do aluno (CEFR). Usado principalmente por professores de idiomas; opcional para outros.',
                max_length=3,
                null=True,
            ),
        ),
    ]
