"""
Envia email de onboarding 24h para usuários que:
- Cadastraram há 23-25 horas
- Possuem assinatura ativa (não apenas trial pendente)
- Ainda não receberam este email

Uso: python manage.py send_onboarding_24h_email

Agendar via cron (ex: a cada hora):
  0 * * * * cd /path/to/project && python manage.py send_onboarding_24h_email
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta

from django.contrib.auth.models import User
from core.models import UserProfile, Subscription


class Command(BaseCommand):
    help = "Envia email de onboarding 24h para usuários com cadastro + assinatura ativa"

    def handle(self, *args, **options):
        try:
            self._run()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro inesperado (sistema continua ok): {e}"))
            # Exit 0 para não falhar o cron no Railway
            return

    def _run(self):
        now = timezone.now()
        # Janela: usuários que cadastraram entre 23h e 25h atrás
        cutoff_start = now - timedelta(hours=25)
        cutoff_end = now - timedelta(hours=23)

        site_url = getattr(settings, 'SITE_URL', 'https://educaflowone.com.br')
        link_login = f"{site_url.rstrip('/')}/login/"
        email_signature = getattr(settings, 'EMAIL_SIGNATURE', '')

        users = User.objects.filter(
            date_joined__gte=cutoff_start,
            date_joined__lte=cutoff_end,
            is_active=True,
            email__isnull=False,
        ).exclude(email='').select_related('profile', 'subscription')

        count = 0
        for user in users:
            # Exige assinatura ativa (usuário precisa ter assinado um plano)
            try:
                if not user.subscription or not user.subscription.is_active:
                    continue
            except Subscription.DoesNotExist:
                continue

            # Já enviou?
            profile = getattr(user, 'profile', None)
            if profile and profile.onboarding_24h_email_sent_at:
                continue

            nome = (user.first_name or '').strip() or (user.get_full_name() or user.username).strip() or 'Você'

            body = f"""Olá, {nome}! 😊

Passaram-se algumas horas desde que você criou sua conta no Educaflow, e queríamos saber: você já começou a usar?

A melhor forma de ver o valor do sistema é com um teste rápido:

👉 Cadastre 1 Aluno
👉 Adicione 1 Aula na Agenda
👉 Registre 1 Planejamento de Aulas ou a sua primeira Cobrança

Leva menos de 2 minutos - e você já começa a ter tudo organizado.

Muitos professores usam o Educaflow justamente para:

✔ Não esquecer cobranças
✔ Controlar mensalidades com facilidade
✔ Ter visão clara do que vão receber no mês

Se quiser continuar agora, é só acessar:

👉 Acessar minha conta
{link_login}

Se tiver qualquer dúvida, é só responder este email ou falar conosco no WhatsApp.

Estamos aqui para ajudar 😊

{email_signature}"""

            try:
                send_mail(
                    subject='Você já cadastrou seu primeiro aluno? 👀',
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                if profile:
                    profile.onboarding_24h_email_sent_at = now
                    profile.save(update_fields=['onboarding_24h_email_sent_at'])
                count += 1
                self.stdout.write(self.style.SUCCESS(f"  Enviado para {user.email} ({user.username})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Erro ao enviar para {user.email}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nConcluído. {count} email(s) enviado(s)."))
