"""Context processors para templates Django"""

from django.utils import timezone

from .models import Subscription


def trial_banner(request):
    """
    Adiciona informações do trial gratuito para exibir banner (dia 5-7).
    Não exibe se o usuário já tem assinatura ativa no Stripe.
    """
    context = {
        'trial_days_left': None,
        'show_trial_banner': False,
        'trial_ends_at': None,
    }
    if not request.user.is_authenticated:
        return context
    try:
        # Quem já tem assinatura Stripe ativa não vê banner de trial
        sub = getattr(request.user, 'subscription', None)
        if sub and sub.stripe_subscription_id and sub.is_active:
            return context
        profile = request.user.profile
        trial_ends = getattr(profile, 'trial_ends_at', None)
        if not trial_ends:
            return context
        now = timezone.now()
        if now >= trial_ends:
            return context
        delta = trial_ends - now
        days_left = delta.days + (1 if delta.seconds > 0 else 0)
        context['trial_days_left'] = max(0, days_left)
        context['trial_ends_at'] = trial_ends
        context['show_trial_banner'] = days_left <= 2
    except Exception:
        pass
    return context
