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
    """Atribui lessons existentes ao primeiro usuário admin ou ao primeiro usuário disponível"""
    Lesson = apps.get_model('core', 'Lesson')
    User = apps.get_model(settings.AUTH_USER_MODEL)
    
    # Tenta encontrar um usuário admin primeiro
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            admin_user = User.objects.first()
        
        if admin_user:
            Lesson.objects.filter(user__isnull=True).update(user=admin_user)
    except Exception as e:
        print(f"Erro ao atribuir usuário às lessons: {e}")
        # Se houver erro, deixa null e o usuário terá que corrigir manualmente
