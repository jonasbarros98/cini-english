# Generated manually - rastreamento do email de recuperação (assinatura pendente)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_add_onboarding_24h_email_sent_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='pending_subscription_recovery_email_sent_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Data/hora em que o email de recuperação (assinatura pendente) foi enviado'),
        ),
    ]
