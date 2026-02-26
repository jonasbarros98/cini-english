# Generated manually - rastreamento do email de onboarding 24h

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_add_public_booking'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='onboarding_24h_email_sent_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Data/hora em que o email de onboarding (24h pós-cadastro) foi enviado'),
        ),
    ]
