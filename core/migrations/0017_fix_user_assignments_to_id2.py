# Generated manually
# Migration para corrigir atribuições de user_id de 1 para 2 (professora piloto)

from django.db import migrations


def fix_user_assignments(apps, schema_editor):
    """Atualiza todos os registros que estão com user_id vazio (null) para user_id=2"""
    User = apps.get_model('auth', 'User')
    
    # Verifica se o usuário ID 2 existe
    target_user = User.objects.filter(id=2).first()
    if not target_user:
        print("Usuário ID 2 não encontrado. Pulando correção.")
        return
    
    # Atualiza Lessons (apenas os que estão com user_id vazio)
    Lesson = apps.get_model('core', 'Lesson')
    updated_lessons = Lesson.objects.filter(user__isnull=True).update(user_id=2)
    if updated_lessons > 0:
        print(f"Atualizados {updated_lessons} lessons de user_id vazio para user_id=2")
    
    # Atualiza Students (apenas os que estão com user_id vazio)
    Student = apps.get_model('core', 'Student')
    updated_students = Student.objects.filter(user__isnull=True).update(user_id=2)
    if updated_students > 0:
        print(f"Atualizados {updated_students} students de user_id vazio para user_id=2")
    
    # Atualiza Tasks (apenas os que estão com user_id vazio)
    Task = apps.get_model('core', 'Task')
    updated_tasks = Task.objects.filter(user__isnull=True).update(user_id=2)
    if updated_tasks > 0:
        print(f"Atualizados {updated_tasks} tasks de user_id vazio para user_id=2")
    
    # Atualiza FinancialEntry - user (apenas os que estão com user_id vazio)
    FinancialEntry = apps.get_model('core', 'FinancialEntry')
    updated_fe_user = FinancialEntry.objects.filter(user__isnull=True).update(user_id=2)
    if updated_fe_user > 0:
        print(f"Atualizados {updated_fe_user} financial entries (user) de user_id vazio para user_id=2")
    
    # Atualiza FinancialEntry - beneficiary_user (apenas os que estão com beneficiary_user_id vazio)
    updated_fe_beneficiary = FinancialEntry.objects.filter(beneficiary_user__isnull=True).update(beneficiary_user_id=2)
    if updated_fe_beneficiary > 0:
        print(f"Atualizados {updated_fe_beneficiary} financial entries (beneficiary_user) de beneficiary_user_id vazio para user_id=2")
    
    # Atualiza LessonPlan (apenas os que estão com user_id vazio)
    LessonPlan = apps.get_model('core', 'LessonPlan')
    updated_plans = LessonPlan.objects.filter(user__isnull=True).update(user_id=2)
    if updated_plans > 0:
        print(f"Atualizados {updated_plans} lesson plans de user_id vazio para user_id=2")
    
    print("Correção de atribuições concluída!")


def reverse_fix_user_assignments(apps, schema_editor):
    """Reverte as alterações (define user_id como null para os registros que foram atribuídos ao ID 2)"""
    # Nota: Como não podemos saber quais registros estavam vazios antes,
    # a reversão define como null apenas os que foram atribuídos nesta migration
    # Isso pode não ser perfeito, mas é o melhor que podemos fazer
    
    # Reverte Lessons (apenas os que foram atribuídos nesta migration)
    Lesson = apps.get_model('core', 'Lesson')
    Lesson.objects.filter(user_id=2).update(user_id=None)
    
    # Reverte Students
    Student = apps.get_model('core', 'Student')
    Student.objects.filter(user_id=2).update(user_id=None)
    
    # Reverte Tasks
    Task = apps.get_model('core', 'Task')
    Task.objects.filter(user_id=2).update(user_id=None)
    
    # Reverte FinancialEntry (user)
    FinancialEntry = apps.get_model('core', 'FinancialEntry')
    FinancialEntry.objects.filter(user_id=2).update(user_id=None)
    
    # Reverte FinancialEntry (beneficiary_user)
    FinancialEntry.objects.filter(beneficiary_user_id=2).update(beneficiary_user_id=None)
    
    # Reverte LessonPlan
    LessonPlan = apps.get_model('core', 'LessonPlan')
    LessonPlan.objects.filter(user_id=2).update(user_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_financialentry_beneficiary_user'),
    ]

    operations = [
        migrations.RunPython(
            code=fix_user_assignments,
            reverse_code=reverse_fix_user_assignments,
        ),
    ]
