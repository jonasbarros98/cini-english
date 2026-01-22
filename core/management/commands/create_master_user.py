import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile


class Command(BaseCommand):
    help = "Cria o usuário master inicial (Admin / Masterkey1502)"

    def handle(self, *args, **options):
        username = os.environ.get("MASTER_USERNAME", "Admin")
        password = os.environ.get("MASTER_PASSWORD", "Masterkey1502")
        email = os.environ.get("MASTER_EMAIL", "admin@educaflowone.com")

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Usuário '{username}' criado com sucesso.")
            )
        else:
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Usuário '{username}' atualizado com sucesso.")
            )

        # Cria ou atualiza o perfil
        profile, profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults={"is_admin": True}
        )
        if not profile_created:
            profile.is_admin = True
            profile.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Usuário master configurado:\n"
                f"  Usuário: {username}\n"
                f"  Senha: {password}\n"
                f"  Admin: Sim"
            )
        )
