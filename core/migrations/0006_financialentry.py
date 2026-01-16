# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_task_date_task_due_date_task_notes'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinancialEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(help_text='Descrição do lançamento', max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, help_text='Valor total', max_digits=10)),
                ('installments', models.PositiveSmallIntegerField(default=1, help_text='Número de parcelas')),
                ('current_installment', models.PositiveSmallIntegerField(default=1, help_text='Parcela atual')),
                ('issue_date', models.DateField(help_text='Data de lançamento')),
                ('due_date', models.DateField(help_text='Data de vencimento')),
                ('payment_date', models.DateField(blank=True, help_text='Data do pagamento', null=True)),
                ('status', models.CharField(choices=[('pending', 'Pendente'), ('paid', 'Pago'), ('overdue', 'Vencido'), ('cancelled', 'Cancelado')], default='pending', max_length=20)),
                ('payment_method', models.CharField(blank=True, choices=[('pix', 'PIX'), ('cash', 'Dinheiro'), ('card', 'Cartão'), ('transfer', 'Transferência'), ('other', 'Outro')], default='pix', max_length=20)),
                ('notes', models.TextField(blank=True, help_text='Observações')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='financial_entries', to='core.student')),
            ],
            options={
                'verbose_name': 'Lançamento Financeiro',
                'verbose_name_plural': 'Lançamentos Financeiros',
                'ordering': ['-due_date', 'student__name'],
            },
        ),
    ]
