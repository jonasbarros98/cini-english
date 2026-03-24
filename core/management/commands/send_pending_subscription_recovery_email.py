"""
Envia email de recuperação para usuários que:
- Cadastraram e iniciaram checkout (têm Subscription com status PENDING)
- Cadastraram há 24-72 horas (dando tempo para voltarem sozinhos)
- Ainda não receberam este email

Assunto: "Faltou só um passo para começar 👀"

Uso: python manage.py send_pending_subscription_recovery_email

Agendar via cron (ex: 1x por dia):
  0 10 * * * cd /path/to/project && python manage.py send_pending_subscription_recovery_email
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta

from django.contrib.auth.models import User
from core.models import UserProfile, Subscription


class Command(BaseCommand):
    help = "Envia email de recuperação para usuários com assinatura pendente (abandonaram no cartão)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours-min',
            type=int,
            default=24,
            help='Horas mínimas desde o cadastro (padrão: 24)'
        )
        parser.add_argument(
            '--hours-max',
            type=int,
            default=72,
            help='Horas máximas desde o cadastro (padrão: 72)'
        )

    def handle(self, *args, **options):
        try:
            self._run(options)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro inesperado (sistema continua ok): {e}"))
            return

    def _run(self, options):
        now = timezone.now()
        hours_min = options['hours_min']
        hours_max = options['hours_max']
        cutoff_start = now - timedelta(hours=hours_max)
        cutoff_end = now - timedelta(hours=hours_min)

        site_url = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br')
        link_pagamento = f"{site_url.rstrip('/')}/planos/"
        email_signature = getattr(settings, 'EMAIL_SIGNATURE', '')

        users = User.objects.filter(
            date_joined__gte=cutoff_start,
            date_joined__lte=cutoff_end,
            is_active=True,
            email__isnull=False,
        ).exclude(email='').select_related('profile', 'subscription')

        count = 0
        for user in users:
            try:
                if not user.subscription or user.subscription.status != Subscription.STATUS_PENDING:
                    continue
            except Subscription.DoesNotExist:
                continue

            profile = getattr(user, 'profile', None)
            if profile and profile.pending_subscription_recovery_email_sent_at:
                continue

            nome = (user.first_name or '').strip() or (user.get_full_name() or user.username).strip() or 'Você'

            body = f"""Olá, {nome} 😊

Percebemos que você iniciou seu cadastro no Educaflow, mas não concluiu a etapa final.

Sua conta já está pronta — falta apenas ativar o teste gratuito para começar a usar.

Com o Educaflow você consegue organizar alunos, agenda e pagamentos em poucos minutos.

👉 Continuar cadastro
{link_pagamento}

Lembrando que você tem 7 dias grátis e pode cancelar quando quiser.

Se tiver qualquer dúvida, estamos aqui para ajudar.

{email_signature}"""

            try:
                send_mail(
                    subject='Faltou só um passo para começar 👀',
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                if profile:
                    profile.pending_subscription_recovery_email_sent_at = now
                    profile.save(update_fields=['pending_subscription_recovery_email_sent_at'])
                count += 1
                self.stdout.write(self.style.SUCCESS(f"  Enviado para {user.email} ({user.username})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Erro ao enviar para {user.email}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nConcluído. {count} email(s) enviado(s)."))
