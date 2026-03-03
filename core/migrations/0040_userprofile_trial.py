# Trial gratuito de 7 dias sem cartão

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_supportticket_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='trial_ends_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Fim do trial gratuito de 7 dias (sem cartão). Após essa data, o usuário precisa assinar.',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='trial_ending_email_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Data em que o email de aviso (trial terminando em 2 dias) foi enviado',
            ),
        ),
    ]
