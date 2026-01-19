# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_fix_user_assignments_to_id2'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='email',
            field=models.EmailField(blank=True, help_text='E-mail do aluno ou responsável', max_length=254),
        ),
        migrations.AddField(
            model_name='student',
            name='status',
            field=models.CharField(
                choices=[('active', 'Ativo'), ('paused', 'Pausado'), ('ended', 'Encerrado')],
                default='active',
                help_text='Status do aluno',
                max_length=10
            ),
        ),
        migrations.AddField(
            model_name='student',
            name='default_due_day',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Dia de vencimento padrão (1 a 28)',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='student',
            name='preferred_payment_method',
            field=models.CharField(
                blank=True,
                choices=[('pix', 'PIX'), ('card', 'Cartão'), ('cash', 'Dinheiro'), ('transfer', 'Transferência')],
                help_text='Forma de pagamento preferida',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='student',
            name='plan_start_date',
            field=models.DateField(blank=True, help_text='Data de início do plano', null=True),
        ),
        migrations.AlterField(
            model_name='student',
            name='pix_key',
            field=models.CharField(blank=True, help_text='Chave Pix', max_length=255),
        ),
        migrations.AlterField(
            model_name='student',
            name='plan_name',
            field=models.CharField(blank=True, help_text='Plano atual', max_length=255),
        ),
        migrations.AlterField(
            model_name='student',
            name='lessons_total',
            field=models.PositiveSmallIntegerField(default=0, help_text='Aulas do plano'),
        ),
        migrations.AlterField(
            model_name='student',
            name='lessons_done',
            field=models.PositiveSmallIntegerField(default=0, help_text='Aulas realizadas'),
        ),
    ]
