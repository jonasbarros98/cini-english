# Generated manually

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_userprofile_user_profile_partner_teachers'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='user',
            field=models.ForeignKey(
                help_text='Professor responsável pela aula',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='lessons',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        # Migração de dados: atribui lessons existentes ao primeiro usuário admin ou ao primeiro usuário
        migrations.RunPython(
            code=lambda apps, schema_editor: _assign_lessons_to_user(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
        # Agora torna o campo obrigatório
        migrations.AlterField(
            model_name='lesson',
            name='user',
            field=models.ForeignKey(
                help_text='Professor responsável pela aula',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='lessons',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]


def _assign_lessons_to_user(apps, schema_editor):
    """Atribui lessons existentes ao usuário ID 2 (professora piloto)"""
    Lesson = apps.get_model('core', 'Lesson')
    User = apps.get_model(settings.AUTH_USER_MODEL)
    
    try:
        # Tenta encontrar o usuário com ID 2 primeiro
        target_user = User.objects.filter(id=2).first()
        if not target_user:
            # Se não existir ID 2, usa o primeiro usuário não-admin
            target_user = User.objects.exclude(id=1).first()
        if not target_user:
            # Último recurso: primeiro usuário disponível
            target_user = User.objects.first()
        
        if target_user:
            Lesson.objects.filter(user__isnull=True).update(user=target_user)
            print(f"Lessons atribuídas ao usuário: {target_user.id} - {target_user.username}")
    except Exception as e:
        print(f"Erro ao atribuir usuário às lessons: {e}")
        # Se houver erro, deixa null e o usuário terá que corrigir manualmente
