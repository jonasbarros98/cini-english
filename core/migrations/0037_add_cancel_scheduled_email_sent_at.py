# Rastreamento do email de cancelamento agendado

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_add_pending_subscription_recovery_email_sent_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='cancel_scheduled_email_sent_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Data em que o email de cancelamento agendado foi enviado'),
        ),
    ]
