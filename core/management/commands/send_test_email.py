"""
Envia um email de teste para CONTACT_EMAIL.
Use para validar Resend/Gmail no Railway:

  railway run python manage.py send_test_email

 ou localmente:
  python manage.py send_test_email
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail


class Command(BaseCommand):
    help = "Envia email de teste para CONTACT_EMAIL (validar Resend/SMTP)"

    def handle(self, *args, **options):
        to = getattr(settings, 'CONTACT_EMAIL', 'educaflowone@gmail.com')
        backend = getattr(settings, 'EMAIL_BACKEND', '?')
        self.stdout.write(f"Backend: {backend}")
        self.stdout.write(f"From: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"To: {to}")
        try:
            n = send_mail(
                subject="[Teste] Email EDUCAflowOne",
                message="Este é um email de teste. Se recebeu, o envio está funcionando.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Email enviado com sucesso (n={n})"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro: {e}"))
            raise
