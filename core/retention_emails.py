"""
Templates de e-mail de retenção (EducaflowOne).
Usados pelo Painel Admin para envio manual com preview editável.

Cada template retorna (subject, html) após interpolação dos dados do usuário.
O marcador __PERSONAL_NOTE__ no HTML é substituído pelo frontend (live preview)
e pelo backend (envio final).
"""

from django.conf import settings

# Nome da plataforma em cópias de e-mail (assinatura, assuntos, corpo)
PLATFORM_NAME = "EducaflowOne"


# ── Metadados dos tipos de e-mail ─────────────────────────────────────────────
EMAIL_TYPE_META = {
    'trial_expiring': {
        'label':    '⏰ Trial expirando',
        'color':    '#b45309',
        'gradient': 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        'cta_color':'#d97706',
    },
    'trial_expired': {
        'label':    '🔴 Trial vencido',
        'color':    '#be123c',
        'gradient': 'linear-gradient(135deg, #f43f5e 0%, #be123c 100%)',
        'cta_color':'#be123c',
    },
    'canceling': {
        'label':    '⚠️ Cancelamento',
        'color':    '#7c3aed',
        'gradient': 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)',
        'cta_color':'#7c3aed',
    },
}


def _personal_note_html(note_text: str, accent_color: str) -> str:
    """Renderiza o bloco de nota pessoal do admin, ou string vazia se sem conteúdo."""
    if not note_text or not note_text.strip():
        return ''
    safe = note_text.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    safe_lines = safe.replace('\n', '<br>')
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0;">
  <tr>
    <td style="background:#fafaf9;border-left:4px solid {accent_color};border-radius:0 12px 12px 0;padding:16px 20px;">
      <p style="margin:0 0 6px;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{accent_color};">Mensagem pessoal</p>
      <p style="margin:0;font-size:14px;color:#374151;line-height:1.7;">{safe_lines}</p>
    </td>
  </tr>
</table>"""


def _base_html(
    header_gradient: str,
    header_emoji: str,
    header_title: str,
    header_subtitle: str,
    body_html: str,
    cta_url: str,
    cta_label: str,
    cta_color: str,
) -> str:
    """Estrutura base dos emails — table-based, inline CSS, compatível com Gmail/Outlook."""
    site = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')
    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN">
<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{header_title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f4f2;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f5f4f2">
<tr><td align="center" style="padding:40px 16px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;">

  <!-- ── HEADER ── -->
  <tr><td style="background:{header_gradient};border-radius:20px 20px 0 0;padding:40px 40px 36px;text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;line-height:1;">{header_emoji}</div>
    <h1 style="margin:0 0 8px;font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-0.03em;line-height:1.25;">{header_title}</h1>
    <p style="margin:0;font-size:15px;color:rgba(255,255,255,0.88);font-weight:500;line-height:1.5;">{header_subtitle}</p>
  </td></tr>

  <!-- ── BODY ── -->
  <tr><td style="background:#ffffff;padding:36px 40px 28px;">

    {body_html}

    <!-- Nota pessoal do admin (substituída pelo JS/backend) -->
    __PERSONAL_NOTE__

    <!-- CTA -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:32px 0 0;">
      <tr><td align="center">
        <a href="{cta_url}"
           style="display:inline-block;background:{cta_color};color:#ffffff;font-size:15px;font-weight:700;
                  text-decoration:none;padding:15px 40px;border-radius:99px;letter-spacing:-0.01em;
                  box-shadow:0 4px 14px rgba(0,0,0,.18);">
          {cta_label} &rarr;
        </a>
      </td></tr>
    </table>

    <p style="margin:20px 0 0;font-size:12.5px;color:#9ca3af;text-align:center;line-height:1.5;">
      Ou acesse: <a href="{site}" style="color:#6b7280;text-decoration:underline;">{site}</a>
    </p>

  </td></tr>

  <!-- ── FOOTER ── -->
  <tr><td style="background:#f9f8f6;border-radius:0 0 20px 20px;padding:24px 40px;text-align:center;border-top:1px solid #ede8e0;">
    <p style="margin:0 0 6px;font-size:12px;color:#9ca3af;font-weight:500;">
      {PLATFORM_NAME}
    </p>
    <p style="margin:0;font-size:11px;color:#c4c4c4;line-height:1.6;">
      Você recebeu este e-mail pois possui uma conta na plataforma.<br>
      <a href="{site}" style="color:#c4c4c4;text-decoration:underline;">www.educaflowone.com.br</a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ── Templates individuais ──────────────────────────────────────────────────────

def _template_trial_expiring(first_name: str, days_left: int, site: str) -> tuple[str, str]:
    days_str = f"{days_left} dia{'s' if days_left != 1 else ''}"
    subject = f"⏰ Seu trial termina em {days_str} — não perca o acesso!"
    body = f"""
    <p style="margin:0 0 16px;font-size:17px;font-weight:700;color:#1c1917;">
      Olá, {first_name}! 👋
    </p>
    <p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">
      Seu período de trial gratuito no <strong>{PLATFORM_NAME}</strong> termina em
      <strong style="color:#b45309;">{days_str}</strong>.
      Não queremos que você perca o acesso a tudo que já configurou!
    </p>

    <!-- Benefícios -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0;">
      <tr><td style="background:#fffbeb;border:1px solid #fde68a;border-radius:14px;padding:20px 24px;">
        <p style="margin:0 0 12px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#b45309;">O que você mantém ao assinar</p>
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:5px 0;font-size:14px;color:#374151;">📚 &nbsp;Todos os seus alunos e aulas cadastradas</td>
          </tr>
          <tr>
            <td style="padding:5px 0;font-size:14px;color:#374151;">💰 &nbsp;Controle financeiro completo</td>
          </tr>
          <tr>
            <td style="padding:5px 0;font-size:14px;color:#374151;">📅 &nbsp;Calendário e planejamento de aulas</td>
          </tr>
          <tr>
            <td style="padding:5px 0;font-size:14px;color:#374151;">📝 &nbsp;Planos de aula e materiais dos alunos</td>
          </tr>
        </table>
      </td></tr>
    </table>

    <p style="margin:16px 0 0;font-size:14px;color:#6b7280;line-height:1.7;">
      Assine agora e continue sem interrupções. É rápido, sem burocracia.
    </p>
    """
    html = _base_html(
        header_gradient=EMAIL_TYPE_META['trial_expiring']['gradient'],
        header_emoji='⏰',
        header_title='Seu trial está acabando!',
        header_subtitle=f'Faltam apenas {days_str} para o fim do seu período gratuito.',
        body_html=body,
        cta_url=f'{site}/planos/',
        cta_label='Assinar agora',
        cta_color=EMAIL_TYPE_META['trial_expiring']['cta_color'],
    )
    return subject, html


def _template_trial_expired(first_name: str, site: str) -> tuple[str, str]:
    subject = f"Sua conta {PLATFORM_NAME} está esperando por você, {first_name} 🎓"
    body = f"""
    <p style="margin:0 0 16px;font-size:17px;font-weight:700;color:#1c1917;">
      Olá, {first_name}! 👋
    </p>
    <p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">
      Seu trial gratuito no <strong>{PLATFORM_NAME}</strong> chegou ao fim, mas
      <strong>sua conta ainda está aqui, com todos os seus dados preservados</strong>.
      Você pode retomar de onde parou a qualquer momento.
    </p>

    <!-- Visual -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0;">
      <tr><td style="background:#fff1f2;border:1px solid #fecdd3;border-radius:14px;padding:20px 24px;text-align:center;">
        <p style="margin:0 0 8px;font-size:32px;line-height:1;">🎓</p>
        <p style="margin:0 0 6px;font-size:16px;font-weight:700;color:#be123c;">Tudo ainda está aqui para você</p>
        <p style="margin:0;font-size:13.5px;color:#6b7280;line-height:1.6;">
          Seus alunos, aulas, histórico financeiro e planejamentos<br>ficam salvos e prontos para quando você voltar.
        </p>
      </td></tr>
    </table>

    <p style="margin:16px 0 0;font-size:15px;color:#374151;line-height:1.7;">
      Escolha o plano que faz sentido para o seu negócio e retome agora mesmo.
      Sem setup, sem perder dados — é como se nunca tivesse parado. 🚀
    </p>
    """
    html = _base_html(
        header_gradient=EMAIL_TYPE_META['trial_expired']['gradient'],
        header_emoji='🔑',
        header_title='Sentimos sua falta!',
        header_subtitle='Sua conta está preservada e pronta para você continuar.',
        body_html=body,
        cta_url=f'{site}/planos/',
        cta_label='Ver planos e voltar',
        cta_color=EMAIL_TYPE_META['trial_expired']['cta_color'],
    )
    return subject, html


def _template_canceling(first_name: str, period_end: str, site: str) -> tuple[str, str]:
    subject = f"💔 Antes de ir, {first_name} — uma mensagem nossa para você"
    body = f"""
    <p style="margin:0 0 16px;font-size:17px;font-weight:700;color:#1c1917;">
      Olá, {first_name}! 💜
    </p>
    <p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">
      Vimos que você agendou o cancelamento da sua assinatura
      {f'para <strong>{period_end}</strong>' if period_end else 'em breve'}.
      Respeitamos sua decisão, mas queríamos ter uma última conversa antes disso.
    </p>

    <!-- O que vão perder -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0;">
      <tr><td style="background:#faf5ff;border:1px solid #ddd6fe;border-radius:14px;padding:20px 24px;">
        <p style="margin:0 0 12px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#7c3aed;">Você vai deixar para trás</p>
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td style="padding:5px 0;font-size:14px;color:#374151;">📊 &nbsp;Histórico completo de alunos e aulas</td></tr>
          <tr><td style="padding:5px 0;font-size:14px;color:#374151;">💰 &nbsp;Controle financeiro organizado</td></tr>
          <tr><td style="padding:5px 0;font-size:14px;color:#374151;">📅 &nbsp;Calendário e planejamentos salvos</td></tr>
          <tr><td style="padding:5px 0;font-size:14px;color:#374151;">🔗 &nbsp;Área do aluno com link personalizado</td></tr>
        </table>
      </td></tr>
    </table>

    <p style="margin:16px 0;font-size:15px;color:#374151;line-height:1.7;">
      Se houver algo que poderíamos ter feito melhor, adoraríamos ouvir.
      E se mudar de ideia, seu acesso continua ativo até o fim do período — é só reativar.
    </p>
    """
    html = _base_html(
        header_gradient=EMAIL_TYPE_META['canceling']['gradient'],
        header_emoji='💔',
        header_title='Antes de você ir...',
        header_subtitle='Valorizamos muito sua presença aqui. Veja o que preparamos para você.',
        body_html=body,
        cta_url=f'{site}/planos/',
        cta_label='Reconsiderar cancelamento',
        cta_color=EMAIL_TYPE_META['canceling']['cta_color'],
    )
    return subject, html


# ── Entrada pública ───────────────────────────────────────────────────────────

def get_retention_email(email_type: str, user, subscription=None) -> tuple[str, str]:
    """
    Retorna (subject, html_with_placeholder) para o tipo de email solicitado.
    O HTML contém __PERSONAL_NOTE__ onde a nota do admin será inserida.
    """
    from django.utils import timezone

    site = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')
    first_name = (user.first_name or user.username or 'você').strip()

    if email_type == 'trial_expiring':
        try:
            profile = user.profile
            days = max(0, (profile.trial_ends_at - timezone.now()).days) if profile.trial_ends_at else 3
        except Exception:
            days = 3
        return _template_trial_expiring(first_name, days, site)

    elif email_type == 'trial_expired':
        return _template_trial_expired(first_name, site)

    elif email_type == 'canceling':
        period_end = ''
        if subscription and subscription.current_period_end:
            period_end = subscription.current_period_end.strftime('%d/%m/%Y')
        return _template_canceling(first_name, period_end, site)

    else:
        raise ValueError(f"Tipo de e-mail desconhecido: {email_type}")


def render_final_email(html_with_placeholder: str, personal_note: str, accent_color: str) -> str:
    """Substitui __PERSONAL_NOTE__ pelo bloco renderizado (ou string vazia)."""
    note_html = _personal_note_html(personal_note, accent_color)
    return html_with_placeholder.replace('__PERSONAL_NOTE__', note_html)
