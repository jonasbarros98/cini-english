# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_lessonplan'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='user_profile',
            field=models.CharField(
                choices=[('professor', 'Professor'), ('prof_parceiro', 'Prof. Parceiro')],
                default='professor',
                help_text='Perfil do usuário no sistema',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='partner_teachers',
            field=models.ManyToManyField(
                blank=True,
                help_text='Professores parceiros vinculados (apenas para perfil Professor)',
                related_name='teachers',
                to='core.userprofile'
            ),
        ),
        migrations.AlterModelOptions(
            name='userprofile',
            options={
                'verbose_name': 'Perfil de Usuário',
                'verbose_name_plural': 'Perfis de Usuários',
            },
        ),
    ]
