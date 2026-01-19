# Generated manually

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_lessonplan_user'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='financialentry',
            name='beneficiary_user',
            field=models.ForeignKey(
                help_text='Professor que receberá o lançamento (pode ser o próprio criador ou um parceiro)',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='beneficiary_financial_entries',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        # Migração de dados: preenche beneficiary_user com o user atual
        migrations.RunPython(
            code=lambda apps, schema_editor: _set_beneficiary_user(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
        # Agora torna o campo obrigatório
        migrations.AlterField(
            model_name='financialentry',
            name='beneficiary_user',
            field=models.ForeignKey(
                help_text='Professor que receberá o lançamento (pode ser o próprio criador ou um parceiro)',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='beneficiary_financial_entries',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]


def _set_beneficiary_user(apps, schema_editor):
    """Preenche beneficiary_user com o user atual (criador)"""
    FinancialEntry = apps.get_model('core', 'FinancialEntry')
    
    try:
        # Atribui beneficiary_user = user para todos os lançamentos existentes
        for entry in FinancialEntry.objects.filter(beneficiary_user__isnull=True):
            entry.beneficiary_user = entry.user
            entry.save()
    except Exception as e:
        print(f"Erro ao preencher beneficiary_user: {e}")
