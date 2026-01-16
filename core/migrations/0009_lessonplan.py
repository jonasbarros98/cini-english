# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_student_contract_pdf'),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(help_text='Data da aula planejada')),
                ('links', models.TextField(blank=True, help_text='Links separados por quebra de linha (Google Slides, YouTube, etc.)')),
                ('goals', models.TextField(blank=True, help_text='Objetivos e metas da aula')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(help_text='Aluno para o qual este planejamento é destinado', on_delete=django.db.models.deletion.CASCADE, related_name='lesson_plans', to='core.student')),
            ],
            options={
                'verbose_name': 'Planejamento de Aula',
                'verbose_name_plural': 'Planejamentos de Aulas',
                'ordering': ['-date', 'student__name'],
            },
        ),
    ]
