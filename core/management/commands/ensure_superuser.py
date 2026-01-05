import os
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Cria ou atualiza um superuser baseado nas variáveis de ambiente"

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin123")

        if not password:
            self.stdout.write(self.style.WARNING(
                "Nenhuma senha definida em DJANGO_SUPERUSER_PASSWORD. Abortando."
            ))
            return

        self.stdout.write(f"Usando superuser: {username} / {email}")

        # get_or_create pelo username
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
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Superuser '{username}' criado com sucesso."
            ))
        else:
            # sempre sincroniza senha e email com o que está no ambiente
            user.set_password(password)
            if email:
                user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Superuser '{username}' atualizado com sucesso."
            ))
