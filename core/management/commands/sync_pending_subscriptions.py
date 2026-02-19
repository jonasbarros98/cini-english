"""
Sincroniza assinaturas pendentes com o Stripe.
Útil quando o webhook não ativou (ex.: trial de 7 dias).
Uso: python manage.py sync_pending_subscriptions [--user-id ID]
"""
from django.core.management.base import BaseCommand
from core.models import Subscription
from core.views import _sync_subscription_from_stripe


class Command(BaseCommand):
    help = "Sincroniza assinaturas pendentes com Stripe (ativa trials, etc.)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Sincronizar apenas este usuário (opcional)",
        )

    def handle(self, *args, **options):
        qs = Subscription.objects.filter(status=Subscription.STATUS_PENDING)
        if options.get("user_id"):
            qs = qs.filter(user_id=options["user_id"])
        count = 0
        for sub in qs:
            try:
                before = sub.status
                _sync_subscription_from_stripe(sub)
                sub.refresh_from_db()
                if sub.status != before:
                    count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  {sub.user.username} (id={sub.user_id}): {before} → {sub.status}"
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  {sub.user.username}: {e}")
                )
        self.stdout.write(self.style.SUCCESS(f"\nConcluído. {count} assinatura(s) atualizada(s)."))
