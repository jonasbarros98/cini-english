# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_stripeevent_subscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='cpf_cnpj',
            field=models.CharField(blank=True, help_text='CPF ou CNPJ', max_length=20),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='phone',
            field=models.CharField(blank=True, help_text='Telefone/WhatsApp', max_length=50),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='cep',
            field=models.CharField(blank=True, help_text='CEP', max_length=10),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='address',
            field=models.CharField(blank=True, help_text='Endereço completo', max_length=255),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='city',
            field=models.CharField(blank=True, help_text='Cidade', max_length=100),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='state',
            field=models.CharField(blank=True, help_text='UF (Estado)', max_length=2),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='timezone',
            field=models.CharField(default='America/Sao_Paulo', help_text='Timezone', max_length=50),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='language',
            field=models.CharField(default='pt-BR', help_text='Idioma preferido', max_length=10),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='photo',
            field=models.ImageField(blank=True, help_text='Foto do perfil', null=True, upload_to='profile_photos/'),
        ),
    ]
