"""
Envia email de aviso quando o trial gratuito termina em ~2 dias (dia 5 do trial).
- Usuários com trial_ends_at entre 1d20h e 2d4h no futuro
- Sem assinatura Stripe ativa (só trial gratuito)
- Ainda não receberam este email

Uso: python manage.py send_trial_ending_email

Agendar via cron (ex: a cada 6 horas):
  0 */6 * * * cd /path/to/project && python manage.py send_trial_ending_email
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta

from core.models import UserProfile


class Command(BaseCommand):
    help = "Envia email de aviso: trial termina em 2 dias (dia 5)"

    def handle(self, *args, **options):
        try:
            self._run()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro inesperado: {e}"))

    def _run(self):
        now = timezone.now()
        # Janela: trial termina em ~2 dias (entre 1d20h e 2d4h)
        window_start = now + timedelta(days=1, hours=20)
        window_end = now + timedelta(days=2, hours=4)

        site_url = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br')
        link_planos = f"{site_url.rstrip('/')}/planos/"
        email_signature = getattr(settings, 'EMAIL_SIGNATURE', '')

        profiles = UserProfile.objects.filter(
            trial_ends_at__gte=window_start,
            trial_ends_at__lte=window_end,
            trial_ending_email_sent_at__isnull=True,
            user__is_active=True,
            user__email__isnull=False,
        ).exclude(user__email='').select_related('user')

        count = 0
        for profile in profiles:
            user = profile.user
            # Só quem NÃO tem assinatura Stripe ativa (está no trial gratuito)
            try:
                sub = user.subscription
                if sub.stripe_subscription_id and sub.is_active:
                    continue
            except Exception:
                pass

            nome = (user.first_name or '').strip() or (user.get_full_name() or user.username).strip() or 'Você'

            body = f"""Olá, {nome}!

Você está há 5 dias usando o Educaflow. Em 2 dias seu período de teste gratuito termina.

Para continuar tendo acesso a tudo que você já organizou (alunos, agenda, planejamentos, cobranças), escolha um plano:

{link_planos}

Nenhum cartão foi pedido até agora - você experimentou sem compromisso. Se gostou, é só assinar e seguir usando.

Qualquer dúvida, responda este email ou fale conosco no WhatsApp.

{email_signature}"""

            try:
                send_mail(
                    subject='Seu trial do Educaflow termina em 2 dias',
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                profile.trial_ending_email_sent_at = now
                profile.save(update_fields=['trial_ending_email_sent_at'])
                count += 1
                self.stdout.write(self.style.SUCCESS(f"  Enviado para {user.email} ({user.username})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Erro ao enviar para {user.email}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nConcluído. {count} email(s) enviado(s)."))
