# Generated manually - Agenda pública de agendamento

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_add_subscription_exempt'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='slug_publico',
            field=models.SlugField(blank=True, help_text='Slug único para link público de agendamento (ex: ayla-barros). Só letras, números e hífens.', max_length=80, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='agenda_publica_ativa',
            field=models.BooleanField(default=False, help_text='Se True, a agenda pública está ativa e o link pode ser compartilhado'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='public_availability',
            field=models.JSONField(blank=True, default=dict, help_text='Horários disponíveis por dia da semana. Formato: {1:[18:00,21:00], 2:[18:00,21:00], ...} (0=domingo, 6=sábado)'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='public_booking_duration',
            field=models.PositiveSmallIntegerField(default=60, help_text='Duração da aula em minutos para agendamento público'),
        ),
        migrations.CreateModel(
            name='PublicBookingRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requested_date', models.DateField(help_text='Data solicitada')),
                ('requested_time', models.TimeField(help_text='Horário solicitado')),
                ('duration_minutes', models.PositiveSmallIntegerField(default=60)),
                ('student_name', models.CharField(max_length=255)),
                ('student_whatsapp', models.CharField(max_length=30)),
                ('student_email', models.EmailField(max_length=254)),
                ('subject', models.CharField(blank=True, max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pendente'), ('confirmed', 'Confirmada'), ('cancelled', 'Cancelada')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('teacher', models.ForeignKey(help_text='Professor que receberá a solicitação', on_delete=django.db.models.deletion.CASCADE, related_name='public_booking_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Solicitação de agendamento público',
                'verbose_name_plural': 'Solicitações de agendamento público',
                'ordering': ['-created_at'],
            },
        ),
    ]
