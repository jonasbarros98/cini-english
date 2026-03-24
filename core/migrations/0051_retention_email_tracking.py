from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_admin_panel_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="last_retention_email_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Data/hora do último e-mail de retenção enviado manualmente pelo admin"
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="last_retention_email_type",
            field=models.CharField(
                blank=True,
                default='',
                max_length=50,
                help_text="Tipo do último e-mail de retenção enviado (trial_expiring, trial_expired, canceling)"
            ),
        ),
    ]
