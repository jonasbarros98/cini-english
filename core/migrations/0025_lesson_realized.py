# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_lessonplanattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='realized',
            field=models.BooleanField(
                default=False,
                help_text='Indica se a aula foi realizada'
            ),
        ),
    ]
