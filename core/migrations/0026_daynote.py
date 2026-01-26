# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_lesson_realized'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='DayNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(help_text='Data da nota (YYYY-MM-DD)')),
                ('text', models.TextField(blank=True, help_text='Texto da observação do dia')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(help_text='Professor responsável pela nota', on_delete=django.db.models.deletion.CASCADE, related_name='day_notes', to='auth.user')),
            ],
            options={
                'verbose_name': 'Nota do Dia',
                'verbose_name_plural': 'Notas do Dia',
                'ordering': ['-date'],
                'unique_together': {('user', 'date')},
            },
        ),
    ]
