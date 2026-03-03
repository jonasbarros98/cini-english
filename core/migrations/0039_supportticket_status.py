# Generated manually - status e resolved_at para tickets

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_student_billing_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportticket',
            name='status',
            field=models.CharField(
                choices=[('open', 'Aberto'), ('closed', 'Concluído')],
                default='open',
                help_text='Status do ticket',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='supportticket',
            name='resolved_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Data em que o ticket foi marcado como concluído',
            ),
        ),
    ]
