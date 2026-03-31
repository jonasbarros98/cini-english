from __future__ import annotations

from typing import List

from django.conf import settings


def render_feature_announcement_email(
    *,
    feature_name: str,
    preview_text: str,
    body_paragraphs: List[str],
    cta_label: str,
    cta_url: str,
    recipient_first_name: str = "Professor",
    recipient_plan_name: str = "",
) -> str:
    """
    Renderiza o HTML final de um email de anúncio de funcionalidade.

    MVP: não usa template file; gera HTML inline compatível com Gmail/Outlook.
    """

    site = getattr(settings, "SITE_URL", "https://www.educaflowone.com.br").rstrip("/")

    def safe(text: str) -> str:
        text = text or ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    feature_name_s = safe(feature_name)
    preview_text_s = safe(preview_text)
    recipient_first_name_s = safe(recipient_first_name)
    cta_label_s = safe(cta_label)
    cta_url_s = safe(cta_url)

    paragraphs_html = "".join(
        f'<p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">{safe(p)}</p>'
        for p in (body_paragraphs or [])
        if p and str(p).strip()
    )

    # NOTE: strings do email (except header/CTA) são geridas pelo admin (campos do formulário).
    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN">
<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{feature_name_s}</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f4f2;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

<!-- Preheader (hidden) -->
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
  {preview_text_s}
  &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
</div>

<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f5f4f2">
  <tr><td align="center" style="padding:40px 16px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;">

      <tr><td style="background:linear-gradient(135deg,#15803d 0%,#166534 100%);border-radius:20px 20px 0 0;padding:40px 40px 36px;text-align:center;">
        <div style="font-size:48px;margin-bottom:16px;line-height:1;">📢</div>
        <h1 style="margin:0 0 8px;font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-0.03em;line-height:1.25;">
          Novo: {feature_name_s}
        </h1>
        <p style="margin:0;font-size:15px;color:rgba(255,255,255,0.88);font-weight:500;line-height:1.5;">
          {preview_text_s}
        </p>
      </td></tr>

      <tr><td style="background:#ffffff;padding:36px 40px 28px;">
        <p style="margin:0 0 20px;font-size:17px;font-weight:700;color:#1c1917;">Olá, {recipient_first_name_s} —</p>

        {paragraphs_html}

        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:32px 0 0;">
          <tr><td align="center">
            <a href="{cta_url_s}"
               style="display:inline-block;background:#15803d;color:#ffffff;font-size:15px;font-weight:700;
                      text-decoration:none;padding:15px 40px;border-radius:99px;letter-spacing:-0.01em;
                      box-shadow:0 4px 14px rgba(0,0,0,.18);">
              {cta_label_s}
            </a>
          </td></tr>
        </table>

        <p style="margin:20px 0 0;font-size:12.5px;color:#9ca3af;text-align:center;line-height:1.5;">
          Ou acesse: <a href="{site}" style="color:#6b7280;text-decoration:underline;">{site}</a>
        </p>
      </td></tr>

      <tr><td style="background:#f9f8f6;border-radius:0 0 20px 20px;padding:24px 40px;text-align:center;border-top:1px solid #ede8e0;">
        <p style="margin:0 0 6px;font-size:12px;color:#9ca3af;font-weight:500;">
          EducaflowOne
        </p>
        <p style="margin:0;font-size:11px;color:#c4c4c4;line-height:1.6;">
          Você recebeu este e-mail pois possui uma conta ativa na plataforma.<br>
          <a href="{site}" style="color:#c4c4c4;text-decoration:underline;">www.educaflowone.com.br</a>
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>

</body>
</html>"""

