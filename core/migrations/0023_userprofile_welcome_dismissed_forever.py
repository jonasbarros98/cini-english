# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_add_profile_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='welcome_dismissed_forever',
            field=models.BooleanField(default=False, help_text='Se True, o popup de boas-vindas não é exibido novamente'),
        ),
    ]
