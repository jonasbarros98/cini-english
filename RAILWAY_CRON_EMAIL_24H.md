# Emails automáticos — Configuração no Railway

Para os emails automáticos funcionarem, você precisa configurar **Cron Jobs** no Railway.

---

## Email 1: Onboarding 24h — "Você já cadastrou seu primeiro aluno?"

Para usuários com cadastro + assinatura ativa há 24h.

---

## Passo a passo no Railway

### 1. Garantir que a migração rodou

A migração roda automaticamente no deploy (veja `preDeployCommand` no `railway.json`). Se você já fez deploy após a alteração, está ok.

### 2. Criar um serviço Cron no Railway

1. Abra o **Railway Dashboard** → seu projeto
2. Clique em **"+ New"** → **"Empty Service"** (ou **"Cron Job"** se aparecer)
3. Conecte o **mesmo repositório** do app principal
4. O Railway vai criar um novo serviço no mesmo projeto

### 3. Configurar o serviço Cron

1. Clique no novo serviço
2. Em **Settings**:
   - **Build Command:** deixe igual ao do app principal (ou vazio se usar o mesmo build)
   - **Start Command:** `python manage.py send_onboarding_24h_email`
   - **Cron Schedule:** `0 * * * *` (a cada hora, no minuto 0)
     - Formato: minuto hora dia mês dia-da-semana
     - `0 * * * *` = todo dia, todo mês, toda hora, no minuto 0

3. Em **Variables** (ou aba "Variables"):
   - Adicione as **mesmas variáveis** do app principal:
     - `DATABASE_URL` (copie do serviço principal)
     - `EMAIL_HOST_USER`
     - `EMAIL_HOST_PASSWORD`
     - `SITE_URL` = `https://educaflowone.com.br` (ou seu domínio)
     - `DJANGO_SECRET_KEY` (para o Django funcionar)
   - Ou use **"Shared Variables"** se o Railway permitir compartilhar variáveis entre serviços

4. **Deploy** o serviço

### 4. Variável SITE_URL

No app principal ou no serviço Cron, adicione (se ainda não tiver):

```
SITE_URL=https://educaflowone.com.br
```

Assim o link de login no email usa o domínio correto.

---

## Resumo rápido

| O quê | Onde |
|------|------|
| Novo serviço | Railway → + New → Empty Service |
| Start Command | `python manage.py send_onboarding_24h_email` |
| Cron Schedule | `0 * * * *` (a cada hora) |
| Variáveis | Mesmas do app principal (DB, EMAIL, SITE_URL etc.) |

---

## Testar manualmente

Para testar sem esperar o cron:

1. Railway → serviço do Cron
2. Aba **"Deployments"** ou **"Run"** → execute o comando manualmente, ou
3. Na sua máquina (com venv ativo):
   ```bash
   python manage.py send_onboarding_24h_email
   ```

Nenhum email será enviado se não houver usuário que se cadastrou há 23–25 horas e tenha assinatura ativa.

---

## Email 2: Recuperação — "Faltou só um passo para começar"

Para usuários que **abandonaram no cartão** (assinatura PENDING), cadastrados há 24–72 horas.

### Comando

```bash
python manage.py send_pending_subscription_recovery_email
```

### Configuração no Railway

Crie outro serviço Cron (ou combine com o existente em um script):

- **Start Command:** `python manage.py send_pending_subscription_recovery_email`
- **Cron Schedule:** `0 10 * * *` (todo dia às 10h UTC, ou ajuste para horário desejado)
