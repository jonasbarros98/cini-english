# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_userprofile'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'core_student'
                        AND column_name = 'contract_pdf'
                    ) THEN
                        ALTER TABLE core_student 
                        ADD COLUMN contract_pdf VARCHAR(100);
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'core_student'
                        AND column_name = 'contract_pdf'
                    ) THEN
                        ALTER TABLE core_student DROP COLUMN contract_pdf;
                    END IF;
                END $$;
            """,
        ),
        migrations.SeparateDatabaseAndState(
            # Não faz nada no banco (a coluna já foi criada pelo RunSQL se necessário)
            database_operations=[],
            # Apenas atualiza o estado do Django
            state_operations=[
                migrations.AddField(
                    model_name='student',
                    name='contract_pdf',
                    field=models.FileField(blank=True, help_text='Contrato do aluno em PDF', null=True, upload_to='contracts/'),
                ),
            ],
        ),
    ]
