# Generated manually for billing type feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_add_cancel_scheduled_email_sent_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='billing_type',
            field=models.CharField(
                choices=[
                    ('package', 'Pacote de aulas'),
                    ('monthly_fixed', 'Mensal fixo'),
                    ('per_lesson', 'Por aula realizada'),
                    ('other', 'Outro'),
                ],
                default='package',
                help_text='Tipo de cobrança do aluno',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='student',
            name='monthly_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Valor mensal fixo (para tipo Mensal fixo)',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='student',
            name='per_lesson_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Valor por aula realizada',
                max_digits=10,
                null=True,
            ),
        ),
    ]
