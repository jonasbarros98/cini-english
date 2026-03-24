from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_retention_email_tracking"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RetentionEmailLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_type", models.CharField(
                    choices=[
                        ("trial_expiring", "⏰ Trial expirando"),
                        ("trial_expired",  "🔴 Trial vencido"),
                        ("canceling",      "⚠️ Cancelamento"),
                    ],
                    max_length=50,
                )),
                ("subject", models.CharField(blank=True, max_length=255)),
                ("personal_note", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="retention_email_logs",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("sent_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="retention_emails_sent",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-sent_at"],
                "verbose_name": "Log de e-mail de retenção",
                "verbose_name_plural": "Logs de e-mails de retenção",
            },
        ),
    ]
