# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_alter_subscription_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='subscription_exempt',
            field=models.BooleanField(default=False, help_text='Se True, o usuário não precisa de assinatura ativa para acessar o sistema (ex: admin, contas internas)'),
        ),
    ]
