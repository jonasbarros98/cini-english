# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0018_add_student_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='BillingLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_type', models.CharField(choices=[('friendly', 'Lembrete amigável'), ('due_today', 'Vence hoje'), ('overdue', 'Em atraso'), ('thank_you', 'Agradecimento')], help_text='Tipo de mensagem enviada', max_length=20)),
                ('send_method', models.CharField(choices=[('whatsapp', 'WhatsApp'), ('email', 'E-mail'), ('sms', 'SMS'), ('other', 'Outro')], default='whatsapp', help_text='Método de envio', max_length=20)),
                ('message_content', models.TextField(help_text='Conteúdo da mensagem enviada')),
                ('sent_at', models.DateTimeField(auto_now_add=True, help_text='Data e hora do envio')),
                ('financial_entry', models.ForeignKey(help_text='Lançamento financeiro cobrado', on_delete=django.db.models.deletion.CASCADE, related_name='billing_logs', to='core.financialentry')),
                ('user', models.ForeignKey(help_text='Professor que realizou a cobrança', on_delete=django.db.models.deletion.CASCADE, related_name='billing_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Log de Cobrança',
                'verbose_name_plural': 'Logs de Cobrança',
                'ordering': ['-sent_at'],
            },
        ),
    ]
