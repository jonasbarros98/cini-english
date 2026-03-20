# Onboarding Automático (Trial) — n8n + Resend (fluxo em produção local)

Este documento descreve o fluxo que está funcionando hoje no seu ambiente:
1. O backend (Django) dispara um webhook no n8n ao iniciar o trial (signup).
2. O n8n aguarda (Delay).
3. O n8n consulta o progresso no backend em `/api/internal/onboarding/progress/`.
4. Com base no `stage` retornado, o n8n envia e-mails via Resend.

Arquivos relevantes no código:
- Backend: `core/views.py` (webhook + endpoint de progresso + cálculo do `stage`)
- Workflow: `docs/n8n/omboarding_check_eduflow.workflow.json`
- Env vars: `.env`

---

## 1) Timeline do fluxo (visão de alto nível)

1. Usuário faz `signup` e o trial começa.
2. No backend, `signup_view` chama `_trigger_n8n_onboarding_webhook(...)` em *fire-and-forget* (thread).
3. O n8n recebe o evento no node `Webhook New User` (URL/UUID do webhook).
4. O n8n espera o tempo configurado (ex.: `Delay 30min`).
5. O n8n chama `GET /api/internal/onboarding/progress/` no backend, informando:
   - `user_id`
   - token de validação (via `X-Internal-Token` ou query param `token`)
6. O backend retorna:
   - `stage`: `missing_student` | `missing_lesson` | `missing_financial` | `activated`
7. O n8n executa o IF correspondente e envia um e-mail com HTML formatado (Resend).

---

## 2) Pré-requisitos (local)

### 2.1 Backend (Django)
O backend precisa estar rodando (ex.: `python manage.py runserver`).

Configurar `.env` com:
- `N8N_ONBOARDING_WEBHOOK_ENABLED=true`
- `N8N_ONBOARDING_WEBHOOK_URL=<URL_PUBLICA_DO_N8N>/webhook-test/<UUID_DO_WORKFLOW>`
- `N8N_ONBOARDING_STATUS_TOKEN=<TOKEN_ÚNICO>`

### 2.2 n8n
- Workflow precisa estar **importado** e **Active**.
- O node `Webhook New User` precisa escutar o **mesmo UUID** da variável `N8N_ONBOARDING_WEBHOOK_URL`.

### 2.3 Resend
- Ter `RESEND_API_KEY` configurada no n8n (ou no workflow, conforme o seu JSON atual).
- O `from` precisa ser um sender/domínio verificado/permitido na Resend (ex.: `onboarding@educaflowone.com.br`).
- Evitar e-mails do tipo “bounced/suppressed” (a Resend bloqueia envio para destinatários na suppression list).

---

## 3) Backend: como o `stage` é calculado

O endpoint de progresso é:
- `GET /api/internal/onboarding/progress/`

Segurança:
- valida `N8N_ONBOARDING_STATUS_TOKEN`
- aceita token tanto em `X-Internal-Token` quanto em query param `token`

Payload enviado ao n8n (no webhook do signup) inclui:
- `event`: `trial_started`
- `user_id`, `username`, `email`, `first_name`, `last_name`
- `trial_ends_at` (se existir)
- `started_at`
- `onboarding_check_url` = URL completa do endpoint de progresso no backend
- `onboarding_check_token` = `N8N_ONBOARDING_STATUS_TOKEN`

Lógica do `stage` hoje (financeiro substituiu homework):
- `missing_student`: não existe aluno para o usuário
- `missing_lesson`: existe aluno, mas não existe aula associada a qualquer aluno do usuário
- `missing_financial`: existe aluno e aula, mas não existe **FinancialEntry** (lançamento financeiro) para os alunos do usuário
- `activated`: aluno + aula + financeiro (ou cobranças) já existem

Importante:
- O backend agora contabiliza `FinancialEntry` para definir `missing_financial`.
- Para compatibilidade com payload antigo, ele mantém campos de homework zerados/não usados (`has_homework: False`, etc.), mas a decisão de `stage` é por financeiro.

---

## 4) n8n: estrutura do workflow

Workflow (padrão):
1. `Webhook New User`
   - Recebe o evento do backend no UUID do webhook
2. `Delay 30min`
   - Aguarda o professor concluir onboarding
3. `Check User Status` (HTTP Request)
   - Chama `onboarding_check_url` + `user_id` + `token`
   - Na sua máquina local (n8n em Docker), a URL do backend pode exigir troca de `localhost/127.0.0.1` para `host.docker.internal`
4. IFs (cadeia)
   - `IF Missing Student` (stage == `missing_student`) → `Email Missing Student`
   - `IF Missing Lesson` (stage == `missing_lesson`) → `Email Missing Lesson`
   - `IF Missing Financial` (stage == `missing_financial`) → `Email Missing Financial`
   - `IF Activated` (stage == `activated`) → `Email Activated` (opcional, mas você optou por manter)

E-mails enviados:
- Node `Email ...` usa `POST https://api.resend.com/emails`
- Monta body com `from`, `to`, `subject` e `html`

---

## 5) Como o fluxo foi ajustado para funcionar na sua máquina local

O ponto mais sensível no local foi:

1. n8n roda em **Docker**
2. Django roda na **máquina host**

Então o n8n não pode acessar `http://localhost:8000` (localhost vira o container do n8n).

Por isso, no node `Check User Status`, a URL do backend foi ajustada para substituir:
- `localhost`/`127.0.0.1` → `host.docker.internal`

Resultado:
- O n8n consegue chamar o endpoint `GET /api/internal/onboarding/progress/` corretamente.

---

## 6) Adaptação para PRD (Railway)

Você pode hospedar o n8n em Railway (ou qualquer outro lugar com URL pública HTTPS). O requisito é:
- A URL do webhook do n8n tem que ser publicamente acessível pelo backend no Railway.

Checklist PRD:
1. Suba o n8n em um ambiente com URL pública HTTPS
2. Atualize no backend (Railway) as env vars:
   - `N8N_ONBOARDING_WEBHOOK_ENABLED=true`
   - `N8N_ONBOARDING_WEBHOOK_URL=<URL_PUBLICA_DO_N8N>/webhook/<UUID>`
   - `N8N_ONBOARDING_STATUS_TOKEN=<mesmo token do workflow>`
3. No workflow do n8n PRD, garanta que o `Check User Status` chama o backend do Railway em URL pública (nunca `localhost`).
4. Valide o `from` e evite destinatários suprimidos na Resend.

---

## 7) Arquivo do workflow usado

Workflow fonte/atual:
- `docs/n8n/omboarding_check_eduflow.workflow.json`

Ele contém o layout HTML dos e-mails (incluindo a trilha com:
- cadastro do aluno
- agendamento de aula
- financeiro/pagamentos (sem homework)
- e o e-mail final em `activated`).

