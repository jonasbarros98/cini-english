# Generated manually

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_task_user'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='financialentry',
            name='user',
            field=models.ForeignKey(
                help_text='Professor responsável pelo lançamento financeiro',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='financial_entries',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        # Migração de dados: atribui financial entries existentes ao primeiro usuário admin ou ao primeiro usuário
        migrations.RunPython(
            code=lambda apps, schema_editor: _assign_financial_entries_to_user(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
        # Agora torna o campo obrigatório
        migrations.AlterField(
            model_name='financialentry',
            name='user',
            field=models.ForeignKey(
                help_text='Professor responsável pelo lançamento financeiro',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='financial_entries',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]


def _assign_financial_entries_to_user(apps, schema_editor):
    """Atribui financial entries existentes ao primeiro usuário admin ou ao primeiro usuário disponível"""
    FinancialEntry = apps.get_model('core', 'FinancialEntry')
    User = apps.get_model(settings.AUTH_USER_MODEL)
    
    # Tenta encontrar um usuário admin primeiro
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            admin_user = User.objects.first()
        
        if admin_user:
            FinancialEntry.objects.filter(user__isnull=True).update(user=admin_user)
    except Exception as e:
        print(f"Erro ao atribuir usuário aos financial entries: {e}")
        # Se houver erro, deixa null e o usuário terá que corrigir manualmente
