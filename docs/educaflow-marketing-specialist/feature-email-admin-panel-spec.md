# Spec: Feature Announcements Panel — Admin Panel

**Documento:** Spec de implementação para agente desenvolvedor (Cursor)
**Data:** 2026-03-25
**Status:** Pronto para implementação
**Contexto:** Extensão do painel em `frontend/templates/admin_panel.html`

---

## 1. Feature Overview

### O que é

Um novo painel dentro da página `/painel-admin/` que permite ao admin compor, pré-visualizar e enviar emails de anuncio de novas funcionalidades para todos os assinantes ativos em um único clique.

### Por que existe

O fluxo atual de retenção (`admin_send_retention_email`) é individual: o admin abre o drawer de um usuario, escolhe um template e envia para aquela pessoa. Nao existe mecanismo nativo para enviar uma comunicacao em massa para toda a base ativa — o que e necessario para anunciar funcionalidades como Arquivos, novas integrações ou atualizações de plano.

### Quem usa

Exclusivamente o admin autenticado (`request.user.profile.is_admin == True`). O mesmo guard já aplicado em `AdminPanelView`, `admin_panel_users_api` e `admin_send_retention_email`.

### Escopo funcional

- Listar campanhas de anuncio enviadas (historico)
- Compor nova campanha: assunto, preview text, conteudo, CTA
- Pre-visualizar o email renderizado em tempo real (iframe, igual ao modal existente)
- Confirmar e enviar para todos os assinantes ativos (excluindo parceiros)
- Registrar cada envio individual no banco para auditoria
- Prevenir reenvio de uma campanha ja marcada como `sent`

---

## 2. UI Spec — Feature Announcements Section

### 2.1 Posicionamento no layout

O painel atual (`admin_panel.html`) nao tem abas — e uma pagina unica com KPI cards, toolbar e tabela de usuarios. A secao de Feature Announcements sera adicionada como uma **nova area abaixo da tabela de usuarios**, separada por um divisor visual, acessada via um segundo conjunto de tabs/toggle na propria pagina.

**Implementacao de navegacao por abas:**

Adicionar dois botoes de tab logo acima do bloco `.table-wrap` (e da nova secao), usando o mesmo estilo `.btn-ghost` ja existente:

```html
<div class="admin-tabs" id="adminTabs">
  <button class="admin-tab active" data-tab="users">👥 Usuarios</button>
  <button class="admin-tab"        data-tab="announcements">📢 Anuncios</button>
</div>
```

CSS para `.admin-tabs` e `.admin-tab` segue o design system existente:

```css
.admin-tabs {
  padding: 20px 32px 0;
  display: flex;
  gap: 8px;
  border-bottom: 1.5px solid var(--border);
  margin: 0 32px;
}
.admin-tab {
  font-family: var(--font);
  font-size: 13px;
  font-weight: 700;
  padding: 10px 18px;
  border-radius: var(--r-sm) var(--r-sm) 0 0;
  border: 1.5px solid transparent;
  border-bottom: none;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: color .15s, background .12s;
  position: relative;
  bottom: -1.5px;
}
.admin-tab:hover { color: var(--text); background: var(--surface-2); }
.admin-tab.active {
  background: var(--surface);
  color: var(--text);
  border-color: var(--border);
  border-bottom-color: var(--surface);
}
```

O JS alterna `.active` entre as tabs e mostra/oculta `#tabUsers` e `#tabAnnouncements` (usando `display:none` / `display:block`).

---

### 2.2 Tab "Usuarios" (existente, sem mudança de conteudo)

O conteudo atual (`.table-wrap` com a tabela de usuarios) e envolvido em:

```html
<div id="tabUsers">
  <!-- conteudo existente: .table-wrap -->
</div>
```

---

### 2.3 Tab "Anuncios" — layout geral

```html
<div id="tabAnnouncements" style="display:none; padding: 24px 32px 80px;">

  <!-- Cabecalho da secao -->
  <div class="ann-header">
    <div>
      <h2 class="ann-title">Anuncios de Funcionalidades</h2>
      <p class="ann-subtitle">Envie emails de anuncio para todos os assinantes ativos.</p>
    </div>
    <button class="btn btn-dark" id="btnNewCampaign">+ Nova campanha</button>
  </div>

  <!-- Tabela de campanhas passadas -->
  <div class="table-card" style="margin-top: 20px;">
    <table id="campaignsTable">
      <thead>
        <tr>
          <th>Titulo interno</th>
          <th>Assunto do email</th>
          <th>Enviado em</th>
          <th>Destinatarios</th>
          <th>Enviado por</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody id="campaignsBody">
        <!-- preenchido via JS -->
      </tbody>
    </table>
  </div>

</div>
```

CSS para o cabecalho da secao:

```css
.ann-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 4px;
}
.ann-title {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -.03em;
  color: var(--text);
  margin-bottom: 4px;
}
.ann-subtitle {
  font-size: 13px;
  color: var(--muted);
  font-weight: 500;
}
```

A tabela `.table-card`, `thead th`, `tbody tr`, `tbody td` reusam exatamente os seletores ja definidos no CSS do arquivo (linhas 202–301).

**Colunas da tabela de campanhas:**

| Coluna | Campo | Formatacao |
|--------|-------|------------|
| Titulo interno | `FeatureEmailCampaign.title` | texto simples |
| Assunto do email | `FeatureEmailCampaign.subject` | texto simples |
| Enviado em | `FeatureEmailCampaign.sent_at` | `fmtDT(iso)` (funcao ja existente no JS) |
| Destinatarios | `FeatureEmailCampaign.recipient_count` | numero inteiro |
| Enviado por | `sent_by.first_name + sent_by.username` | texto simples |
| Status | `FeatureEmailCampaign.status` | badge colorido (ver abaixo) |

**Badge de status:**

```css
.status-badge-draft { background: var(--surface-3); color: var(--muted); border: 1px solid var(--border); }
.status-badge-sent  { background: var(--act-bg); color: var(--act-c); border: 1px solid var(--act-b); }
```

Linhas com status `sent` nao exibem botao de acao. Linhas com status `draft` exibem um botao `.btn-row-open` com texto "Editar →".

---

### 2.4 Modal de composicao / envio

O modal de Feature Announcement segue exatamente o mesmo padrao do modal de retenção existente (`#emailModal`, classe `.em-overlay`), com dois paineis lado a lado:

- **Painel esquerdo** (340px fixo, classe `.em-left`): formulario de composicao
- **Painel direito** (flex:1, classe `.em-right`): iframe de preview

**ID e classes do novo modal:**

```html
<div class="em-overlay" id="featureEmailModal">
  <div class="em-wrap" style="max-width:1080px; height:90vh;">

    <!-- Painel esquerdo -->
    <div class="em-left" style="width:380px;">
      <div class="em-head">
        <div>
          <span class="em-type-badge"
            style="background:#ecfdf5;color:#15803d;border:1px solid #bbf7d0;border-radius:99px;padding:3px 10px;font-size:11px;font-weight:700;">
            Nova Funcionalidade
          </span>
          <div class="em-user-info" id="featureEmailRecipientInfo"></div>
        </div>
        <button class="drawer-x" onclick="closeFeatureEmailModal()">×</button>
      </div>

      <div class="em-fields" id="featureEmailFields">

        <div class="em-field">
          <label class="em-label">Titulo interno <span class="em-label-hint">nao aparece no email</span></label>
          <input type="text" id="feCampaignTitle" class="d-input"
            placeholder="ex: Lancamento Arquivos — Marco 2026">
        </div>

        <div class="em-field">
          <label class="em-label">Assunto do email</label>
          <input type="text" id="feSubject" class="d-input em-subject-input"
            placeholder="ex: Chega de procurar PDF no WhatsApp">
        </div>

        <div class="em-field">
          <label class="em-label">Preview text <span class="em-label-hint">pre-header, ~85 chars</span></label>
          <input type="text" id="fePreviewText" class="d-input"
            placeholder="ex: Faca upload uma vez. Envie para qualquer aluno, quando quiser.">
        </div>

        <div class="em-field">
          <label class="em-label">Nome da funcionalidade <span class="em-label-hint">destaque no header</span></label>
          <input type="text" id="feFeatureName" class="d-input"
            placeholder="ex: Arquivos">
        </div>

        <div class="em-field">
          <label class="em-label">Paragrafo 1</label>
          <textarea id="feBody1" class="d-input d-textarea"
            placeholder="Introducao — contexto e dor que a funcionalidade resolve."></textarea>
        </div>

        <div class="em-field">
          <label class="em-label">Paragrafo 2 <span class="em-label-hint">opcional</span></label>
          <textarea id="feBody2" class="d-input d-textarea"
            placeholder="Detalhe adicional, beneficios ou instrucoes."></textarea>
        </div>

        <div class="em-field">
          <label class="em-label">Paragrafo 3 <span class="em-label-hint">opcional</span></label>
          <textarea id="feBody3" class="d-input d-textarea"
            placeholder="Encerramento, call-to-action textual ou nota de plano."></textarea>
        </div>

        <div class="em-field">
          <label class="em-label">Texto do botao CTA</label>
          <input type="text" id="feCTALabel" class="d-input"
            placeholder="ex: Abrir meus Arquivos">
        </div>

        <div class="em-field">
          <label class="em-label">URL do botao CTA</label>
          <input type="url" id="feCTAURL" class="d-input"
            placeholder="ex: https://educaflowone.com.br/arquivos/">
        </div>

      </div><!-- /em-fields -->

      <div class="em-foot">
        <button class="btn btn-cancel" onclick="closeFeatureEmailModal()">Cancelar</button>
        <button class="btn" id="fePreviewBtn"
          style="background:var(--surface-2);color:var(--text-2);border:1.5px solid var(--border-2);"
          onclick="updateFeatureEmailPreview()">
          Atualizar preview
        </button>
        <button class="btn btn-send" id="feSendBtn" onclick="openFeatureSendConfirm()">
          Enviar para todos →
        </button>
      </div>
    </div><!-- /em-left -->

    <!-- Painel direito: preview -->
    <div class="em-right">
      <div class="em-preview-bar">
        <span class="em-preview-label">Pre-visualizacao</span>
        <span class="em-preview-to" id="fePreviewTo">Personalizando com dados de exemplo</span>
      </div>
      <iframe id="fePreviewFrame" class="em-iframe" sandbox="allow-same-origin"></iframe>
    </div>

  </div>
</div>
```

**Live preview:** O preview e atualizado ao clicar "Atualizar preview". O iframe usa `srcdoc` com o HTML renderizado retornado pelo endpoint `GET /api/admin/feature-email-preview/` com os valores atuais dos campos. Um debounce de 600ms nos inputs `feSubject`, `feFeatureName`, `feBody1`, `feBody2`, `feBody3`, `feCTALabel` tambem dispara o preview automaticamente.

---

### 2.5 Modal de confirmacao de envio

Reutiliza o padrao `.resend-popup-overlay` / `.resend-popup` ja existente no arquivo:

```html
<div class="resend-popup-overlay" id="featureSendConfirm">
  <div class="resend-popup">
    <div class="resend-popup-icon">📢</div>
    <h3>Confirmar envio</h3>
    <p id="featureSendConfirmMsg">
      Este email sera enviado para <strong id="featureRecipientCount">—</strong> assinantes ativos.
      Esta acao nao pode ser desfeita.
    </p>
    <div class="resend-popup-actions">
      <button class="btn" onclick="closeFeatureSendConfirm()">Cancelar</button>
      <button class="btn btn-send" id="featureConfirmSendBtn" onclick="sendFeatureCampaign()">
        Confirmar e enviar
      </button>
    </div>
  </div>
</div>
```

O `featureRecipientCount` e preenchido com o valor retornado por `GET /api/admin/feature-email-recipient-count/` ao abrir o modal de confirmacao.

---

## 3. Email HTML Template Spec

### 3.1 Estrutura base

O template segue exatamente o padrao de `_base_html()` em `core/retention_emails.py`:

- Wrapper outer: `<table width="100%">` com `bgcolor="#f5f4f2"`
- Container inner: `max-width:560px`, centralizado
- Header: gradiente de fundo, emoji, titulo H1, subtitulo
- Body: `background:#ffffff`, `padding:36px 40px 28px`
- CTA: botao pill com `border-radius:99px`, `box-shadow:0 4px 14px rgba(0,0,0,.18)`
- Footer: `background:#f9f8f6`, `border-radius:0 0 20px 20px`, `border-top:1px solid #ede8e0`
- Font: `'Helvetica Neue',Helvetica,Arial,sans-serif`
- Body background: `#f5f4f2`
- Todos os estilos inline (compatibilidade Gmail/Outlook)

**Diferenca do template de retencao:** O template de Feature Announcement **nao tem** o bloco `__PERSONAL_NOTE__`. Em vez disso, aceita multiplos paragrafos de corpo como lista e uma tabela de planos (opcional) renderizada conforme o conteudo.

### 3.2 Palette de cores para Feature Announcements

| Elemento | Valor |
|----------|-------|
| Header gradient | `linear-gradient(135deg, #15803d 0%, #166534 100%)` |
| CTA button color | `#15803d` |
| Accent color (destaques inline) | `#15803d` |
| Header text | `#ffffff` |

Esta palette (verde) diferencia visualmente os anuncios de funcionalidade dos emails de retencao (ambar, vermelho, violeta).

### 3.3 Parametros do template

| Parametro | Tipo | Obrigatorio | Descricao |
|-----------|------|-------------|-----------|
| `subject` | str | Sim | Assunto do email (nao aparece no HTML, usado no envio) |
| `preview_text` | str | Sim | Texto do pre-header (max 85 chars recomendado) |
| `feature_name` | str | Sim | Nome da funcionalidade — aparece no header H1 e no corpo em bold |
| `body_paragraphs` | list[str] | Sim | Lista de 1-3 strings. Cada string vira um `<p>` no corpo |
| `cta_label` | str | Sim | Texto do botao |
| `cta_url` | str | Sim | URL do botao |
| `recipient_first_name` | str | Sim | Primeiro nome do professor (fallback: "professor") |
| `recipient_plan_name` | str | Nao | Nome do plano (Basic/Premium/Platinum). Se vazio, omite a linha do plano |

### 3.4 HTML completo do template

```python
def render_feature_announcement_email(
    feature_name: str,
    preview_text: str,
    body_paragraphs: list,
    cta_label: str,
    cta_url: str,
    recipient_first_name: str = 'professor',
    recipient_plan_name: str = '',
) -> str:
    """
    Renderiza o HTML final de um email de anuncio de funcionalidade.
    Retorna a string HTML completa pronta para envio.
    Nao usa __PERSONAL_NOTE__ — paragrafos sao passados diretamente.
    """
    from django.conf import settings
    site = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')

    def safe(text):
        return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    paragraphs_html = ''.join(
        f'<p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">{safe(p)}</p>'
        for p in body_paragraphs if p and p.strip()
    )

    plan_line = ''
    if recipient_plan_name:
        plan_line = f'''
        <p style="margin:16px 0 0;font-size:13.5px;color:#6b7280;line-height:1.6;">
          Voce esta no plano <strong style="color:#15803d;">{safe(recipient_plan_name)}</strong>.
        </p>'''

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN">
<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{safe(feature_name)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f4f2;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

<!-- Preheader oculto -->
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
  {safe(preview_text)}
  &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
</div>

<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f5f4f2">
<tr><td align="center" style="padding:40px 16px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;">

  <!-- HEADER -->
  <tr><td style="background:linear-gradient(135deg,#15803d 0%,#166534 100%);border-radius:20px 20px 0 0;padding:40px 40px 36px;text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;line-height:1;">✨</div>
    <h1 style="margin:0 0 8px;font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-0.03em;line-height:1.25;">
      Novo: {safe(feature_name)}
    </h1>
    <p style="margin:0;font-size:15px;color:rgba(255,255,255,0.88);font-weight:500;line-height:1.5;">
      {safe(preview_text)}
    </p>
  </td></tr>

  <!-- BODY -->
  <tr><td style="background:#ffffff;padding:36px 40px 28px;">

    <p style="margin:0 0 20px;font-size:17px;font-weight:700;color:#1c1917;">
      Oi, {safe(recipient_first_name)} —
    </p>

    {paragraphs_html}

    {plan_line}

    <!-- CTA -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:32px 0 0;">
      <tr><td align="center">
        <a href="{cta_url}"
           style="display:inline-block;background:#15803d;color:#ffffff;font-size:15px;font-weight:700;
                  text-decoration:none;padding:15px 40px;border-radius:99px;letter-spacing:-0.01em;
                  box-shadow:0 4px 14px rgba(0,0,0,.18);">
          {safe(cta_label)} &rarr;
        </a>
      </td></tr>
    </table>

    <p style="margin:20px 0 0;font-size:12.5px;color:#9ca3af;text-align:center;line-height:1.5;">
      Ou acesse: <a href="{site}" style="color:#6b7280;text-decoration:underline;">{site}</a>
    </p>

  </td></tr>

  <!-- FOOTER -->
  <tr><td style="background:#f9f8f6;border-radius:0 0 20px 20px;padding:24px 40px;text-align:center;border-top:1px solid #ede8e0;">
    <p style="margin:0 0 6px;font-size:12px;color:#9ca3af;font-weight:500;">
      EducaflowOne
    </p>
    <p style="margin:0;font-size:11px;color:#c4c4c4;line-height:1.6;">
      Voce recebeu este e-mail pois possui uma conta ativa na plataforma.<br>
      <a href="{site}" style="color:#c4c4c4;text-decoration:underline;">www.educaflowone.com.br</a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
```

Esta funcao deve ser adicionada a `core/retention_emails.py` (ou a um novo modulo `core/feature_emails.py` — preferencia pelo novo modulo para nao poluir o arquivo existente).

### 3.5 Render de exemplo com conteudo do email de Arquivos

Abaixo esta o render de parametros derivado do conteudo de `docs/educaflow-marketing-specialist/email-anuncio-arquivos.md`. Este e o exemplo que o developer pode usar para testar o template visualmente:

```python
render_feature_announcement_email(
    feature_name="Arquivos",
    preview_text="Faca upload uma vez. Envie para qualquer aluno, quando quiser — direto pelo EducaflowOne.",
    body_paragraphs=[
        "Voce ja perdeu tempo procurando aquele PDF que mandou para um aluno no mes passado? "
        "Faz parte da rotina de quase todo professor particular: o material esta no Drive, ou no WhatsApp, "
        "ou na pasta do notebook — e na hora de reusar, voce baixa, procura o aluno certo, reenvia. De novo.",

        "Agora voce tem um espaco so seu para guardar PDFs, audios, videos, imagens e links — tudo organizado "
        "com busca, filtros e tags, no mesmo lugar onde voce ja gerencia seus alunos e agenda. "
        "Suba uma vez, use com quantos alunos quiser. Encontre rapido. Envie direto para o aluno com um clique.",

        "Experimente agora: acesse o Arquivos, suba tres materiais que voce mais reutiliza e envie um para um aluno. "
        "Leva menos de dois minutos.",
    ],
    cta_label="Abrir meus Arquivos",
    cta_url="https://educaflowone.com.br/arquivos/",
    recipient_first_name="Ana",
    recipient_plan_name="Premium",
)
```

---

## 4. Backend Spec

### 4.1 Novo modelo: `FeatureEmailCampaign`

Arquivo: `core/models.py`

```python
class FeatureEmailCampaign(models.Model):
    """Campanha de email de anuncio de funcionalidade. Enviada para toda a base ativa."""

    STATUS_DRAFT = 'draft'
    STATUS_SENT  = 'sent'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Rascunho'),
        (STATUS_SENT,  'Enviado'),
    ]

    # Metadados internos (nao aparecem no email)
    title = models.CharField(
        max_length=255,
        help_text="Titulo interno da campanha (nao aparece no email)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )

    # Conteudo do email
    subject = models.CharField(max_length=255, help_text="Assunto do email")
    preview_text = models.CharField(
        max_length=200,
        blank=True,
        help_text="Texto pre-header (aparece apos o assunto em clientes de email)"
    )
    feature_name = models.CharField(
        max_length=100,
        help_text="Nome da funcionalidade — aparece no header e no corpo"
    )
    body_json = models.JSONField(
        default=list,
        help_text="Lista de strings: cada item e um paragrafo do corpo do email"
    )
    cta_label = models.CharField(max_length=100, help_text="Texto do botao CTA")
    cta_url   = models.URLField(help_text="URL de destino do botao CTA")

    # Auditoria de envio
    sent_at        = models.DateTimeField(null=True, blank=True)
    sent_by        = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='feature_campaigns_sent',
    )
    recipient_count = models.PositiveIntegerField(
        default=0,
        help_text="Numero de destinatarios no momento do envio"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Campanha de email de funcionalidade'
        verbose_name_plural = 'Campanhas de email de funcionalidade'

    def __str__(self):
        return f"{self.title} — {self.get_status_display()}"
```

---

### 4.2 Novo modelo: `FeatureEmailLog`

Arquivo: `core/models.py`

```python
class FeatureEmailLog(models.Model):
    """Log de envio individual de uma campanha de anuncio. Um registro por destinatario."""

    STATUS_SENT   = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_SENT,   'Enviado'),
        (STATUS_FAILED, 'Falhou'),
    ]

    campaign = models.ForeignKey(
        FeatureEmailCampaign,
        on_delete=models.CASCADE,
        related_name='logs',
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='feature_email_logs',
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    status  = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SENT,
    )
    error_message = models.TextField(
        blank=True,
        help_text="Mensagem de erro em caso de falha no envio"
    )

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Log de email de funcionalidade'
        verbose_name_plural = 'Logs de emails de funcionalidade'
        # Cada usuario recebe cada campanha no maximo uma vez
        unique_together = [('campaign', 'user')]

    def __str__(self):
        return f"{self.campaign.title} → {self.user.email} [{self.status}]"
```

**Nota de design:** `unique_together = [('campaign', 'user')]` e o guardrail de banco de dados para prevenir duplicatas no mesmo nivel de `FeatureEmailLog`. A prevencao principal (campanha ja `sent`) e feita na view antes de processar.

---

### 4.3 Novas views

Arquivo: `core/views.py`

#### View 1: `feature_email_campaigns_list` — `GET /api/admin/feature-campaigns/`

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feature_email_campaigns_list(request):
    """
    Lista todas as campanhas de email de funcionalidade.
    Restrito a admin.
    """
    try:
        if not request.user.profile.is_admin:
            return Response({'detail': 'Forbidden'}, status=403)
    except Exception:
        return Response({'detail': 'Forbidden'}, status=403)

    from .models import FeatureEmailCampaign
    campaigns = FeatureEmailCampaign.objects.select_related('sent_by').all()

    data = []
    for c in campaigns:
        data.append({
            'id':              c.id,
            'title':           c.title,
            'subject':         c.subject,
            'preview_text':    c.preview_text,
            'feature_name':    c.feature_name,
            'body_json':       c.body_json,
            'cta_label':       c.cta_label,
            'cta_url':         c.cta_url,
            'status':          c.status,
            'sent_at':         c.sent_at.isoformat() if c.sent_at else None,
            'sent_by':         (c.sent_by.first_name or c.sent_by.username) if c.sent_by else None,
            'recipient_count': c.recipient_count,
            'created_at':      c.created_at.isoformat(),
        })

    return Response({'campaigns': data})
```

---

#### View 2: `feature_email_recipient_count` — `GET /api/admin/feature-email-recipient-count/`

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feature_email_recipient_count(request):
    """
    Retorna o numero de destinatarios que receberao a proxima campanha.
    Logica identica ao filtro de envio (assinantes ativos, sem parceiros).
    """
    try:
        if not request.user.profile.is_admin:
            return Response({'detail': 'Forbidden'}, status=403)
    except Exception:
        return Response({'detail': 'Forbidden'}, status=403)

    recipients = _get_feature_email_recipients()
    return Response({'count': recipients.count()})
```

---

#### View 3: `feature_email_preview` — `GET /api/admin/feature-email-preview/`

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feature_email_preview(request):
    """
    Renderiza o HTML do email de anuncio com dados de exemplo para preview.
    Query params: feature_name, preview_text, body_1, body_2, body_3, cta_label, cta_url
    O preview usa first_name='Professor' e plan_name='Premium' como placeholders.
    """
    try:
        if not request.user.profile.is_admin:
            return Response({'detail': 'Forbidden'}, status=403)
    except Exception:
        return Response({'detail': 'Forbidden'}, status=403)

    from .feature_emails import render_feature_announcement_email

    p = request.query_params
    body_paragraphs = [
        p.get('body_1', ''),
        p.get('body_2', ''),
        p.get('body_3', ''),
    ]
    body_paragraphs = [b for b in body_paragraphs if b.strip()]

    html = render_feature_announcement_email(
        feature_name=p.get('feature_name', 'Nova Funcionalidade'),
        preview_text=p.get('preview_text', ''),
        body_paragraphs=body_paragraphs or ['Conteudo do email aparecera aqui.'],
        cta_label=p.get('cta_label', 'Acessar agora'),
        cta_url=p.get('cta_url', 'https://educaflowone.com.br'),
        recipient_first_name='Professor',
        recipient_plan_name='Premium',
    )

    return Response({'html': html})
```

---

#### View 4: `send_feature_email_campaign` — `POST /api/admin/send-feature-campaign/`

```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_feature_email_campaign(request):
    """
    Cria e envia uma campanha de email de anuncio para todos os assinantes ativos.

    Body JSON:
    {
        "title":        str,   # titulo interno
        "subject":      str,   # assunto do email
        "preview_text": str,   # pre-header
        "feature_name": str,   # nome da funcionalidade
        "body_json":    list,  # lista de paragrafos
        "cta_label":    str,
        "cta_url":      str
    }

    Logica:
    1. Valida campos obrigatorios
    2. Cria FeatureEmailCampaign com status='draft'
    3. Resolve lista de destinatarios via _get_feature_email_recipients()
    4. Renderiza HTML personalizado para cada usuario
    5. Envia via django.core.mail.EmailMessage (backend ja configurado: Resend/SMTP)
    6. Cria FeatureEmailLog por usuario (status: sent/failed)
    7. Atualiza campanha: status='sent', sent_at=now, recipient_count=N, sent_by=admin
    8. Retorna resumo
    """
    try:
        if not request.user.profile.is_admin:
            return Response({'detail': 'Forbidden'}, status=403)
    except Exception:
        return Response({'detail': 'Forbidden'}, status=403)

    from .models import FeatureEmailCampaign, FeatureEmailLog
    from .feature_emails import render_feature_announcement_email
    from django.core.mail import EmailMessage as DjangoEmailMessage

    data = request.data

    # Validacao
    required = ['title', 'subject', 'feature_name', 'body_json', 'cta_label', 'cta_url']
    for field in required:
        if not data.get(field):
            return Response({'detail': f'Campo obrigatorio: {field}'}, status=400)

    body_json = data['body_json']
    if not isinstance(body_json, list) or not any(p.strip() for p in body_json if p):
        return Response({'detail': 'body_json deve ser uma lista com ao menos um paragrafo.'}, status=400)

    # Cria campanha como draft
    campaign = FeatureEmailCampaign.objects.create(
        title=data['title'].strip(),
        subject=data['subject'].strip(),
        preview_text=data.get('preview_text', '').strip(),
        feature_name=data['feature_name'].strip(),
        body_json=body_json,
        cta_label=data['cta_label'].strip(),
        cta_url=data['cta_url'].strip(),
        status=FeatureEmailCampaign.STATUS_DRAFT,
        sent_by=request.user,
    )

    # Resolve destinatarios
    recipients = _get_feature_email_recipients()
    total = recipients.count()

    sent_count   = 0
    failed_count = 0
    logs_to_create = []

    for user in recipients.iterator():
        first_name = (user.first_name or user.username or 'professor').strip()

        # Resolve nome do plano
        plan_name = ''
        try:
            sub = user.subscription
            if sub and sub.is_active:
                plan_name = sub.tier.capitalize()
        except Exception:
            pass

        try:
            html = render_feature_announcement_email(
                feature_name=campaign.feature_name,
                preview_text=campaign.preview_text,
                body_paragraphs=[p for p in campaign.body_json if p and p.strip()],
                cta_label=campaign.cta_label,
                cta_url=campaign.cta_url,
                recipient_first_name=first_name,
                recipient_plan_name=plan_name,
            )
            msg = DjangoEmailMessage(
                subject=campaign.subject,
                body=html,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            msg.content_subtype = 'html'
            msg.send(fail_silently=False)

            logs_to_create.append(FeatureEmailLog(
                campaign=campaign,
                user=user,
                status=FeatureEmailLog.STATUS_SENT,
            ))
            sent_count += 1

        except Exception as e:
            logs_to_create.append(FeatureEmailLog(
                campaign=campaign,
                user=user,
                status=FeatureEmailLog.STATUS_FAILED,
                error_message=str(e)[:500],
            ))
            failed_count += 1

    # Bulk insert dos logs
    FeatureEmailLog.objects.bulk_create(logs_to_create, ignore_conflicts=True)

    # Atualiza campanha para 'sent'
    campaign.status         = FeatureEmailCampaign.STATUS_SENT
    campaign.sent_at        = timezone.now()
    campaign.recipient_count = sent_count
    campaign.save(update_fields=['status', 'sent_at', 'recipient_count', 'updated_at'])

    return Response({
        'success':      True,
        'campaign_id':  campaign.id,
        'sent_count':   sent_count,
        'failed_count': failed_count,
        'total':        total,
    })
```

---

#### Funcao auxiliar de filtragem de destinatarios

Adicionar como funcao modular em `core/views.py`, proxima das outras views admin:

```python
def _get_feature_email_recipients():
    """
    Retorna queryset de usuarios que recebem emails de anuncio de funcionalidade.

    Incluidos:
    - Usuarios com Subscription.status == 'active' (STATUS_ACTIVE)
    - Sem cancel_at_period_end relevante — assinantes ativos recebem mesmo cancelando
      (voce pode decidir excluir cancel_at_period_end=True se preferir)

    Excluidos:
    - Usuarios com profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
    - Usuarios sem email cadastrado
    - Admins (profile.is_admin == True)
    """
    from .models import UserProfile, Subscription

    return (
        User.objects
        .select_related('profile', 'subscription')
        .filter(
            subscription__status=Subscription.STATUS_ACTIVE,
            email__isnull=False,
        )
        .exclude(email='')
        .exclude(profile__user_profile=UserProfile.PROFILE_PARTNER_TEACHER)
        .exclude(profile__is_admin=True)
    )
```

**Nota sobre cancel_at_period_end:** Assinantes com `cancel_at_period_end=True` ainda tem acesso ativo. A decisao de incluir ou excluir este segmento e do admin. A implementacao padrao os inclui. Se a politica mudar, adicionar `.exclude(subscription__cancel_at_period_end=True)`.

---

### 4.4 Novas URLs

Arquivo: `core/urls.py`

Adicionar os seguintes imports na lista de imports da view:

```python
from .views import (
    # ... imports existentes ...
    feature_email_campaigns_list,
    feature_email_recipient_count,
    feature_email_preview,
    send_feature_email_campaign,
)
```

Adicionar no `urlpatterns`, agrupado com as outras rotas `api/admin/`:

```python
# Feature Email Campaigns (admin only)
path("api/admin/feature-campaigns/",           feature_email_campaigns_list,    name="api-admin-feature-campaigns"),
path("api/admin/feature-email-recipient-count/", feature_email_recipient_count, name="api-admin-feature-email-recipient-count"),
path("api/admin/feature-email-preview/",       feature_email_preview,           name="api-admin-feature-email-preview"),
path("api/admin/send-feature-campaign/",       send_feature_email_campaign,     name="api-admin-send-feature-campaign"),
```

Rotas existentes adjacentes (para referencia de posicionamento no arquivo):

```python
path("api/admin/email-preview/", admin_email_preview, name="api-admin-email-preview"),
path("api/admin/send-retention-email/", admin_send_retention_email, name="api-admin-send-retention-email"),
```

---

### 4.5 Novo modulo de email

Arquivo: `core/feature_emails.py` (novo arquivo)

Criar este arquivo com a funcao `render_feature_announcement_email` descrita na secao 3.4. O modulo segue o mesmo padrao de `core/retention_emails.py`: importado nas views apenas quando necessario (dentro do bloco da view), nao no topo do arquivo `views.py`.

---

### 4.6 Migration

Criar migracao com:

```bash
python manage.py makemigrations core --name="add_feature_email_campaign_and_log"
```

A migracao criara duas tabelas:

- `core_featureemailcampaign`
- `core_featureemaillog`

A `unique_together` em `FeatureEmailLog` gera um indice composto em `(campaign_id, user_id)`.

Verificar se `django.db.models.JSONField` esta disponivel (Django 3.1+). O projeto ja usa `JSONField` em `UserProfile.public_availability` (linha 776 de `models.py`), portanto esta disponivel.

---

## 5. Sending Logic Guardrails

### 5.1 Quem recebe

| Criterio | Valor |
|----------|-------|
| `subscription.status` | `active` |
| `profile.user_profile` | `professor` (nao `prof_parceiro`) |
| `profile.is_admin` | `False` |
| `user.email` | nao vazio |

A logica esta encapsulada em `_get_feature_email_recipients()`. Nunca replicar este filtro ad-hoc nas views — sempre chamar a funcao.

**Fundamento para exclusao de parceiros:** O perfil `prof_parceiro` tem acesso restrito a funcionalidades como Arquivos (retorna 403 via API). Enviar anuncio de funcionalidade para parceiro gera expectativa falsa. Este guardrail esta documentado em `docs/educaflow-marketing-specialist/email-anuncio-arquivos.md`.

### 5.2 Prevencao de reenvio

Uma campanha com `status == 'sent'` nao pode ser reenviada. O frontend impede o envio desabilitando o botao para campanhas `sent` na tabela. O backend nao tem validacao adicional contra reenvio de uma campanha existente (pois a view `send_feature_email_campaign` sempre cria uma nova campanha), mas o `unique_together` em `FeatureEmailLog` previne duplicatas de log caso haja bug.

Se no futuro o admin precisar "reenviar", o fluxo correto e criar uma nova campanha (novo titulo interno).

### 5.3 Batching para bases grandes

O loop de envio usa `.iterator()` para nao carregar todos os usuarios em memoria de uma vez. Para bases com mais de 500 usuarios, considerar:

1. **Opcao A (simples):** Adicionar `time.sleep(0.05)` entre envios para nao saturar a API do Resend (rate limit: 100 emails/segundo no plano free, 2 emails/segundo no plano gratuito da Resend). Verificar limite atual no dashboard Resend.

2. **Opcao B (recomendada para escala):** Mover o loop de envio para uma Celery task assincrona. A view cria a campanha e retorna imediatamente; a task envia em background e atualiza o status. Esta opcao requer adicionar Celery ao projeto (nao configurado atualmente).

3. **Opcao C (minimo viavel atual):** Manter sincrono, adicionar timeout generoso no request (o admin aguarda o envio completar). Funcional para bases de ate ~200 usuarios sem risco de timeout de 30s.

A implementacao inicial deve usar a Opcao C (sincrono com `.iterator()`). Se o timeout se tornar problema, migrar para Opcao A ou B.

### 5.4 Retry e tratamento de falhas parciais

O envio nao e atomico: se metade dos emails for enviada e o processo falhar, a campanha ficara em estado inconsistente. Para mitigar:

- O `FeatureEmailLog` com `status='failed'` registra cada falha individual
- O campo `error_message` armazena o traceback resumido (max 500 chars)
- A view retorna `sent_count` e `failed_count` no response — o admin ve no toast quantos falharam
- Nao ha mecanismo de retry automatico. Se necessario, o admin deve criar nova campanha para os que falharam (ou implementar uma view de re-run que filtra usuarios sem log `sent` para aquela campanha)

---

## 6. Integration Checklist

Lista ordenada de todos os arquivos que precisam ser alterados ou criados:

---

### 6.1 `core/models.py`
**O que adicionar:** Duas novas classes apos `RetentionEmailLog` (linha 1300).
- Classe `FeatureEmailCampaign` com todos os campos especificados na secao 4.1
- Classe `FeatureEmailLog` com FK para campanha e usuario, campo `status`, `error_message`, e `unique_together` (secao 4.2)

---

### 6.2 `core/feature_emails.py` *(novo arquivo)*
**O que criar:** Modulo com a funcao `render_feature_announcement_email(...)` conforme secao 3.4.

---

### 6.3 `core/views.py`
**O que adicionar:**
- Funcao `_get_feature_email_recipients()` — proxima das views admin existentes (ap. linha 7600)
- View `feature_email_campaigns_list` (GET)
- View `feature_email_recipient_count` (GET)
- View `feature_email_preview` (GET)
- View `send_feature_email_campaign` (POST)

Todas as quatro views seguem o mesmo padrao de autorizacao das views admin existentes: checar `request.user.profile.is_admin` logo no inicio, retornar 403 se falso.

---

### 6.4 `core/urls.py`
**O que adicionar:**
- 4 imports na lista de imports do `from .views import (...)`
- 4 novas entradas em `urlpatterns`, agrupadas com as rotas `api/admin/` existentes (apos a linha 151 do arquivo atual)

---

### 6.5 `core/migrations/XXXX_add_feature_email_campaign_and_log.py` *(novo arquivo)*
**O que fazer:** Gerar via `python manage.py makemigrations core --name="add_feature_email_campaign_and_log"`. Nao editar manualmente.

---

### 6.6 `frontend/templates/admin_panel.html`
**O que adicionar:**

1. **CSS:** Estilos para `.admin-tabs`, `.admin-tab` (secao 2.1), `.ann-header`, `.ann-title`, `.ann-subtitle` (secao 2.3), `.status-badge-draft`, `.status-badge-sent` (secao 2.3) — adicionar ao bloco `<style>` existente antes de `</style>`

2. **HTML — tabs:** Wrapper `<div class="admin-tabs">` com dois botoes, inserido logo antes de `<div class="table-wrap">` (linha 680 do arquivo atual)

3. **HTML — wrapper da tabela existente:** Envolver o bloco `<div class="table-wrap">...</div>` em `<div id="tabUsers">...</div>`

4. **HTML — nova aba de anuncios:** Adicionar `<div id="tabAnnouncements" style="display:none;">` com cabecalho e tabela de campanhas (secao 2.3), imediatamente apos o fechamento de `</div>` do `#tabUsers`

5. **HTML — modal de composicao:** Adicionar `<div class="em-overlay" id="featureEmailModal">` (secao 2.4) antes de `</body>`

6. **HTML — modal de confirmacao:** Adicionar `<div class="resend-popup-overlay" id="featureSendConfirm">` (secao 2.5) antes de `</body>`

7. **JavaScript:** Adicionar bloco de JS para Feature Announcements ap. apos o bloco de `// ── Email retention` existente (linha 1202). Funcoes necessarias:
   - `loadCampaigns()` — GET `/api/admin/feature-campaigns/`, popula `#campaignsBody`
   - `renderCampaignsTable(campaigns)` — renderiza linhas da tabela
   - `openNewCampaignModal()` — abre `#featureEmailModal`, limpa campos
   - `closeFeatureEmailModal()` — fecha modal
   - `updateFeatureEmailPreview()` — GET `/api/admin/feature-email-preview/` com params dos campos, injeta no `#fePreviewFrame.srcdoc`
   - `openFeatureSendConfirm()` — GET `/api/admin/feature-email-recipient-count/`, preenche `#featureRecipientCount`, abre `#featureSendConfirm`
   - `closeFeatureSendConfirm()` — fecha modal de confirmacao
   - `sendFeatureCampaign()` — POST `/api/admin/send-feature-campaign/`, trata loading/erro/sucesso, chama `loadCampaigns()` ao final

   Adicionar ao `DOMContentLoaded`:
   ```javascript
   document.querySelector('.admin-tab[data-tab="users"]').addEventListener('click', () => switchTab('users'));
   document.querySelector('.admin-tab[data-tab="announcements"]').addEventListener('click', () => switchTab('announcements'));
   document.getElementById('btnNewCampaign').addEventListener('click', openNewCampaignModal);
   ```

   Funcao `switchTab(tab)`:
   ```javascript
   function switchTab(tab) {
     document.querySelectorAll('.admin-tab').forEach(t =>
       t.classList.toggle('active', t.dataset.tab === tab));
     document.getElementById('tabUsers').style.display        = tab === 'users'         ? '' : 'none';
     document.getElementById('tabAnnouncements').style.display = tab === 'announcements' ? '' : 'none';
     if (tab === 'announcements') loadCampaigns();
   }
   ```

   O debounce de 600ms para o preview:
   ```javascript
   let fePreviewDebounce;
   ['feFeatureName','feBody1','feBody2','feBody3','feCTALabel','fePreviewText'].forEach(id => {
     document.getElementById(id).addEventListener('input', () => {
       clearTimeout(fePreviewDebounce);
       fePreviewDebounce = setTimeout(updateFeatureEmailPreview, 600);
     });
   });
   ```

---

## Notas finais para o desenvolvedor

- **Ordem de implementacao recomendada:** models.py → makemigrations → feature_emails.py → views.py → urls.py → admin_panel.html
- **Nao renomear** `_get_feature_email_recipients` — e referenciada por duas views
- **Nao alterar** `admin_send_retention_email` nem `RetentionEmailLog` — nenhuma dependencia cruzada
- **Testar** o preview com os parametros de exemplo da secao 3.5 antes de testar o envio real
- **Verificar** o rate limit atual do plano Resend antes do primeiro envio em producao (secao 5.3)
- O campo `header-pill` no header HTML atual diz "Retencao". Considerar atualizar para "Retencao & Anuncios" ou adicionar um segundo pill ao lado ao implementar as tabs
