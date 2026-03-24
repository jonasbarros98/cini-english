from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_studentmaterial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="admin_notes",
            field=models.TextField(
                blank=True,
                default='',
                help_text="Notas internas do admin sobre este usuário (não visível para o usuário)"
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="last_contacted_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Data/hora do último contato realizado pelo admin com este usuário"
            ),
        ),
    ]
