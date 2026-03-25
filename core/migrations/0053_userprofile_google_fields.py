from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0052_retention_email_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="google_sub",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="ID estável da conta Google (claim sub)",
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="google_picture_url",
            field=models.URLField(
                blank=True,
                default="",
                help_text="Foto de perfil (URL) enviada pelo Google",
                max_length=2048,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="google_hosted_domain",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Domínio Google Workspace (claim hd), se existir",
                max_length=255,
            ),
        ),
    ]
