import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Cria um superusuário padrão se ele ainda não existir."

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "TrocaIsso123!")

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(
                f"Superuser '{username}' já existe. Nada a fazer."
            ))
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Superuser '{username}' criado com sucesso."
        ))
