# Generated manually
# Migration para corrigir atribuições de user_id de 1 para 2 (professora piloto)

from django.db import migrations


def fix_user_assignments(apps, schema_editor):
    """Atualiza todos os registros que estão com user_id=1 para user_id=2"""
    User = apps.get_model('auth', 'User')
    
    # Verifica se o usuário ID 2 existe
    target_user = User.objects.filter(id=2).first()
    if not target_user:
        print("Usuário ID 2 não encontrado. Pulando correção.")
        return
    
    # Atualiza Lessons
    Lesson = apps.get_model('core', 'Lesson')
    updated_lessons = Lesson.objects.filter(user_id=1).update(user_id=2)
    if updated_lessons > 0:
        print(f"Atualizados {updated_lessons} lessons de user_id=1 para user_id=2")
    
    # Atualiza Students
    Student = apps.get_model('core', 'Student')
    updated_students = Student.objects.filter(user_id=1).update(user_id=2)
    if updated_students > 0:
        print(f"Atualizados {updated_students} students de user_id=1 para user_id=2")
    
    # Atualiza Tasks
    Task = apps.get_model('core', 'Task')
    updated_tasks = Task.objects.filter(user_id=1).update(user_id=2)
    if updated_tasks > 0:
        print(f"Atualizados {updated_tasks} tasks de user_id=1 para user_id=2")
    
    # Atualiza FinancialEntry (user)
    FinancialEntry = apps.get_model('core', 'FinancialEntry')
    updated_fe_user = FinancialEntry.objects.filter(user_id=1).update(user_id=2)
    if updated_fe_user > 0:
        print(f"Atualizados {updated_fe_user} financial entries (user) de user_id=1 para user_id=2")
    
    # Atualiza FinancialEntry (beneficiary_user)
    updated_fe_beneficiary = FinancialEntry.objects.filter(beneficiary_user_id=1).update(beneficiary_user_id=2)
    if updated_fe_beneficiary > 0:
        print(f"Atualizados {updated_fe_beneficiary} financial entries (beneficiary_user) de user_id=1 para user_id=2")
    
    # Atualiza LessonPlan
    LessonPlan = apps.get_model('core', 'LessonPlan')
    updated_plans = LessonPlan.objects.filter(user_id=1).update(user_id=2)
    if updated_plans > 0:
        print(f"Atualizados {updated_plans} lesson plans de user_id=1 para user_id=2")
    
    print("Correção de atribuições concluída!")


def reverse_fix_user_assignments(apps, schema_editor):
    """Reverte as alterações (atribui de volta ao ID 1)"""
    User = apps.get_model('auth', 'User')
    admin_user = User.objects.filter(id=1).first()
    
    if not admin_user:
        print("Usuário ID 1 não encontrado. Pulando reversão.")
        return
    
    # Reverte Lessons
    Lesson = apps.get_model('core', 'Lesson')
    Lesson.objects.filter(user_id=2).update(user_id=1)
    
    # Reverte Students
    Student = apps.get_model('core', 'Student')
    Student.objects.filter(user_id=2).update(user_id=1)
    
    # Reverte Tasks
    Task = apps.get_model('core', 'Task')
    Task.objects.filter(user_id=2).update(user_id=1)
    
    # Reverte FinancialEntry (user)
    FinancialEntry = apps.get_model('core', 'FinancialEntry')
    FinancialEntry.objects.filter(user_id=2).update(user_id=1)
    
    # Reverte FinancialEntry (beneficiary_user)
    FinancialEntry.objects.filter(beneficiary_user_id=2).update(beneficiary_user_id=1)
    
    # Reverte LessonPlan
    LessonPlan = apps.get_model('core', 'LessonPlan')
    LessonPlan.objects.filter(user_id=2).update(user_id=1)


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
