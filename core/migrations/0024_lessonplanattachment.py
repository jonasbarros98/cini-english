# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_userprofile_welcome_dismissed_forever'),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonPlanAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(help_text='Arquivo anexado (PDF, Word, Excel, etc.)', upload_to='lesson_plan_attachments/%Y/%m/')),
                ('original_filename', models.CharField(help_text='Nome original do arquivo', max_length=255)),
                ('file_size', models.PositiveIntegerField(help_text='Tamanho do arquivo em bytes')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('lesson_plan', models.ForeignKey(help_text='Planejamento ao qual este anexo pertence', on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='core.lessonplan')),
            ],
            options={
                'verbose_name': 'Anexo de Planejamento',
                'verbose_name_plural': 'Anexos de Planejamentos',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
