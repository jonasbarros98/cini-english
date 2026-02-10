# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_alter_student_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='tier',
            field=models.CharField(
                choices=[('basic', 'Basic'), ('premium', 'Premium'), ('platinum', 'Platinum')],
                default='basic',
                help_text='Tier do plano (Basic, Premium, Platinum)',
                max_length=20
            ),
        ),
    ]
