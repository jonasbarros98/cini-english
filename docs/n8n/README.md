# Automação WhatsApp + EducaFlowOne Onboarding — Documentação PRD

**Última atualização:** 2026-03-19
**Autor:** Jonas Barros
**Stack:** Evolution API · n8n · Django · Resend · Railway · Claude API · Open-Meteo

---

## Índice

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Ambiente Local — WhatsApp (Evolution API + n8n)](#2-ambiente-local--whatsapp-evolution-api--n8n)
3. [Workflow: Bom Dia Bianca](#3-workflow-bom-dia-bianca)
4. [Workflow: Onboarding EducaFlowOne](#4-workflow-onboarding-educaflowone)
5. [Workflow: Trial Ending (e-mail fim de trial)](#5-workflow-trial-ending-e-mail-fim-de-trial)
6. [Produção — n8n no Railway](#6-produção--n8n-no-railway)
7. [Variáveis de Ambiente (referência completa)](#7-variáveis-de-ambiente-referência-completa)
8. [Manutenção e Troubleshooting](#8-manutenção-e-troubleshooting)

---

## 1. Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    PRODUÇÃO (Railway)                    │
│                                                          │
│  ┌─────────────────┐     ┌──────────────────────────┐   │
│  │  cini-english   │────▶│         n8n              │   │
│  │  (Django/       │     │  n8n-cini-english.up.    │   │
│  │  EducaFlowOne)  │◀────│  railway.app             │   │
│  │  educaflowone   │     └──────────────────────────┘   │
│  │  .com.br        │              │                      │
│  └─────────────────┘              │ Resend API           │
│           │                       ▼                      │
│  ┌─────────────────┐     ┌──────────────────────────┐   │
│  │    Postgres     │     │      Postgres-ECuC       │   │
│  │  (app database) │     │    (n8n database)        │   │
│  └─────────────────┘     └──────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  LOCAL (Docker Desktop)                  │
│                                                          │
│  ┌──────────────────┐    ┌─────────────────────────┐    │
│  │  evolution-api   │    │          n8n            │    │
│  │  :8080           │    │         :5678           │    │
│  └──────────────────┘    └─────────────────────────┘    │
│  ┌──────────────────┐    ┌─────────────────────────┐    │
│  │ evolution-redis  │    │   evolution-postgres     │    │
│  │  :6379           │    │       :5432             │    │
│  └──────────────────┘    └─────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**Dois ambientes independentes:**
- **Local**: WhatsApp pessoal (Evolution API) + automações pessoais (n8n local)
- **Produção Railway**: Onboarding EducaFlowOne (n8n Railway) disparado pelo Django

---

## 2. Ambiente Local — WhatsApp (Evolution API + n8n)

### 2.1 Estrutura de arquivos

```
whatsapp-scheduler/
├── docker-compose.yml          # Orquestra todos os containers
├── Dockerfile.evolution        # Imagem customizada com fix do Baileys
├── evolution/                  # Dados da instância WhatsApp (volume)
├── n8n/                        # Dados do n8n local (volume)
├── postgres-data/              # Dados do PostgreSQL local (volume)
├── bom-dia-bianca.workflow.json
├── Onboarding EducaFlowOne - Check Ativação.json   # workflow DEV
├── Onboarding EducaFlowOne - PRD.json              # workflow PRD
├── onboarding-trial-automation-flow.md
└── README.md                   # este arquivo
```

### 2.2 Subir o ambiente local

```powershell
cd "C:\Users\jonas\OneDrive\Documentos\Claude-work\PROJECTS\whatsapp-scheduler"

# Primeira vez (ou após docker compose down -v): rebuild da imagem
docker compose build evolution-api
docker compose up -d

# Demais vezes
docker compose up -d
```

### 2.3 Containers e portas

| Container           | Imagem                          | Porta  |
|---------------------|---------------------------------|--------|
| evolution-api       | evolution-api-patched:latest    | 8080   |
| evolution-postgres  | postgres:15                     | 5432   |
| evolution-redis     | redis:7-alpine                  | 6379   |
| n8n                 | n8nio/n8n:latest                | 5678   |

- **Evolution API Manager**: `http://localhost:8080/manager`
- **n8n local**: `http://localhost:5678`

### 2.4 Fix crítico do Baileys (root cause documentado)

**Problema:** O WhatsApp passou a rejeitar silenciosamente a versão do Baileys hardcoded na imagem `atendai/evolution-api:latest`. A versão `2.3000.1015901307` estava obsoleta. O Baileys entrava em crash loop sem gerar QR code.

**Causa raiz:** O arquivo `/evolution/.env` dentro do container tinha `CONFIG_SESSION_PHONE_VERSION=2.3000.1015901307`. O docker-compose não conseguia sobrescrever porque o app carregava o `.env` interno com `override: true`.

**Fix aplicado no `Dockerfile.evolution`:**
```dockerfile
FROM atendai/evolution-api:latest

RUN sed -i 's/CONFIG_SESSION_PHONE_VERSION=.*/CONFIG_SESSION_PHONE_VERSION=2.3000.1035194821/' /evolution/.env \
    && sed -i 's/AUTHENTICATION_API_KEY=.*/AUTHENTICATION_API_KEY=minha-chave-secreta-123/' /evolution/.env \
    && echo "\nVERSION=2,3000,1035194821" >> /evolution/.env
```

**Versão válida confirmada:** `2.3000.1035194821` (`IS_LATEST=true` em 2026-03-18)

**Como atualizar quando WhatsApp mudar novamente:**
```javascript
// Rodar dentro do container para buscar versão atual:
// docker run --rm --entrypoint node -w /evolution atendai/evolution-api:latest -e "
const { fetchLatestBaileysVersion } = require('baileys');
fetchLatestBaileysVersion().then(({version}) => console.log(version.join(',')));
// "
// Atualizar Dockerfile.evolution com o número retornado
// docker compose build evolution-api && docker compose up -d
```

### 2.5 Conectar/reconectar WhatsApp

```powershell
# 1. Verificar se instância está conectada
Invoke-WebRequest -Uri "http://localhost:8080/instance/fetchInstances" `
  -Headers @{"apikey"="minha-chave-secreta-123"} -UseBasicParsing |
  Select-Object -ExpandProperty Content

# 2. Se connectionStatus != "open", gerar QR code
# Acessar http://localhost:8080/manager e escanear com WhatsApp
# OU via endpoint:
Invoke-WebRequest -Uri "http://localhost:8080/instance/connect/meu-whatsapp" `
  -Headers @{"apikey"="minha-chave-secreta-123"} -UseBasicParsing |
  Select-Object -ExpandProperty Content
# O base64 do QR será retornado — salvo automaticamente como qrcode.png
```

**Credenciais Evolution API local:**
- API Key: `minha-chave-secreta-123`
- Nome da instância: `meu-whatsapp`
- Número conectado: `554198982437` (Jonas)

---

## 3. Workflow: Bom Dia Bianca

**Arquivo:** `bom-dia-bianca.workflow.json`
**n8n:** local (`http://localhost:5678`)
**Agendamento:** Todo dia às 7h (Curitiba = UTC-3 → cron `0 10 * * *`)

### 3.1 Fluxo

```
Schedule (7h) → Buscar Clima (Open-Meteo) → Formatar, Gerar e Enviar (Code)
```

O node "Formatar, Gerar e Enviar" faz 3 coisas em sequência via `this.helpers.httpRequest`:
1. Formata dados do clima (temperatura, condição, dica de treino)
2. Chama Claude API para gerar mensagem personalizada
3. Envia via Evolution API para o WhatsApp da Bianca

### 3.2 APIs utilizadas

| Serviço     | Endpoint                                   | Auth             |
|-------------|--------------------------------------------|------------------|
| Open-Meteo  | `api.open-meteo.com/v1/forecast`           | Sem autenticação |
| Claude API  | `api.anthropic.com/v1/messages`            | API Key          |
| Evolution   | `evolution-api:8080/message/sendText/...`  | apikey header    |

**Parâmetros Open-Meteo (Curitiba):**
- latitude: `-25.4297`, longitude: `-49.2711`
- timezone: `America/Sao_Paulo`

**Contato Bianca:** `554192394289`

**Modelo Claude:** `claude-haiku-4-5-20251001`

### 3.3 Nota sobre this.helpers.httpRequest

O sandbox do n8n bloqueia `fetch`, `require('https')` e `$helpers`. O método correto para chamadas HTTP em Code nodes é `this.helpers.httpRequest(options)` com `json: true` para serialização automática.

---

## 4. Workflow: Onboarding EducaFlowOne

### 4.1 Arquivos

| Arquivo                                             | Uso          |
|-----------------------------------------------------|--------------|
| `Onboarding EducaFlowOne - Check Ativação.json`     | DEV (local)  |
| `Onboarding EducaFlowOne - PRD.json`                | PRD (Railway)|

### 4.2 Fluxo completo

```
Django signup
    │
    ▼ POST (fire-and-forget thread)
Webhook New User (n8n)
    │
    ▼ wait 30 minutos
Check User Status
GET /api/internal/onboarding/progress/?user_id=X&token=Y
    │
    ├─ stage: missing_student   → Email: "Crie seu primeiro aluno"
    ├─ stage: missing_lesson    → Email: "Agende sua primeira aula"
    ├─ stage: missing_financial → Email: "Registre seus pagamentos"
    └─ stage: activated         → Email: "Boa! Você já entendeu como funciona 🎉"
```

### 4.3 Backend Django (core/views.py)

**Endpoint de progresso:**
```
GET /api/internal/onboarding/progress/?user_id={id}&token={token}
```

Segurança: valida `N8N_ONBOARDING_STATUS_TOKEN` via `X-Internal-Token` ou query param.

**Lógica de stages:**
- `missing_student`: nenhum aluno cadastrado para o usuário
- `missing_lesson`: tem aluno, mas sem aula agendada
- `missing_financial`: tem aluno e aula, mas sem `FinancialEntry`
- `activated`: aluno + aula + financeiro existem

**Payload enviado ao n8n no signup:**
```json
{
  "event": "trial_started",
  "user_id": 123,
  "username": "joao",
  "email": "joao@exemplo.com",
  "first_name": "João",
  "last_name": "Silva",
  "trial_ends_at": "2026-04-18T00:00:00Z",
  "started_at": "2026-03-19T10:00:00Z",
  "onboarding_check_url": "https://www.educaflowone.com.br/api/internal/onboarding/progress/",
  "onboarding_check_token": "<N8N_ONBOARDING_STATUS_TOKEN>"
}
```

### 4.4 Node Check User Status — URL dinâmica

O node monta a URL a partir do payload recebido:
```javascript
={{
  (($json.body.onboarding_check_url || $json.onboarding_check_url || '')
    .replace('127.0.0.1','host.docker.internal')
    .replace('localhost','host.docker.internal'))
}}?user_id={{($json.body.user_id || $json.user_id)}}&token={{($json.body.onboarding_check_token || $json.onboarding_check_token)}}
```

- **Local (DEV):** substitui `localhost` → `host.docker.internal` (Docker não acessa localhost do host)
- **Produção (PRD):** o Django gera a URL pública (`educaflowone.com.br`), o replace é no-op

### 4.5 Emails (Resend API)

- **From:** `EducaFlowOne <onboarding@educaflowone.com.br>`
- **API Key:** variável `RESEND_API_KEY` no n8n (Railway) ou credencial Header Auth — **nunca** commitar chave no JSON
- **Endpoint:** `POST https://api.resend.com/emails`

**Diferença DEV → PRD:**

| Campo         | DEV                         | PRD                         |
|---------------|-----------------------------|-----------------------------|
| Delay         | 3 minutos (teste)           | 30 minutos                  |
| active        | true                        | false (ativar manualmente)  |
| instanceId    | hash local                  | limpo (Railway gera novo)   |

---

## 5. Workflow: Trial Ending (e-mail fim de trial)

Automação **diária** (cron `0 8 * * *`) que avisa usuários cujo **trial gratuito termina em ~2 dias**, marca envio idempotente no Django e usa **Resend** para o e-mail.

### 5.1 Arquivo e importação

| Arquivo | Uso |
|---------|-----|
| `docs/n8n/Trial Ending - EducaFlowOne - oficial.json` | Importar no n8n (Railway ou local) |
| `docs/n8n/trial_ending_endpoints.py` | Referência; **a implementação vive em** `core/views.py` |

### 5.2 Endpoints Django (já integrados)

| Método | Caminho | Descrição |
|--------|---------|-----------|
| `GET` | `/api/internal/trial-ending-users/` | Lista `{ "users": [ { user_id, email, first_name, username, trial_ends_at } ] }` |
| `POST` | `/api/internal/mark-trial-email-sent/` | Body JSON `{"user_id": 123}` — define `trial_ending_email_sent_at` |

**Auth:** mesmo token que o onboarding — `N8N_ONBOARDING_STATUS_TOKEN` via header `X-Internal-Token` ou query `?token=` / `?onboarding_check_token=`.

**Critérios da lista (resumo):** `trial_ends_at` entre **now+44h e now+52h**, `trial_ending_email_sent_at` nulo, `subscription_exempt=False`, sem `Subscription` com status `active`.

### 5.3 Configuração no n8n

1. Substituir `{{ COLOCAR_TOKEN_AQUI }}` nos nodes HTTP pelo **mesmo** valor de `N8N_ONBOARDING_STATUS_TOKEN` (ou usar variável/credencial n8n).
2. No serviço n8n (Railway), definir **`RESEND_API_KEY`** — o workflow usa `Authorization: Bearer {{ $env.RESEND_API_KEY }}`.
3. Ajustar URLs dos nodes se o domínio não for produção (ex.: `localhost` em DEV).
4. No node **IF Has Users**, se o HTTP Request devolver o JSON dentro de `body`, use algo como `{{ $json.body.users.length }}` em vez de `{{ $json.users.length }}`.

---

## 6. Produção — n8n no Railway

### 6.1 Serviços Railway

| Serviço       | Descrição                   | URL / Host interno              |
|---------------|-----------------------------|---------------------------------|
| cini-english  | Django EducaFlowOne         | `www.educaflowone.com.br`       |
| Postgres      | Banco do Django             | `postgres.railway.internal`     |
| n8n           | Automação (workflows PRD)   | `n8n-cini-english.up.railway.app` |
| Postgres-ECuC | Banco exclusivo do n8n      | `postgres-ecuc.railway.internal`|

### 6.2 Variáveis do serviço n8n no Railway

```env
# Servidor
N8N_HOST=0.0.0.0
N8N_PORT=5678
PORT=5678
N8N_PROTOCOL=https
WEBHOOK_URL=https://n8n-cini-english.up.railway.app

# Auth
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<senha configurada>

# Banco de dados (Postgres-ECuC)
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=${{Postgres-ECuC.PGHOST}}
DB_POSTGRESDB_PORT=${{Postgres-ECuC.PGPORT}}
DB_POSTGRESDB_DATABASE=${{Postgres-ECuC.PGDATABASE}}
DB_POSTGRESDB_USER=${{Postgres-ECuC.PGUSER}}
DB_POSTGRESDB_PASSWORD=${{Postgres-ECuC.PGPASSWORD}}

# Segurança
N8N_ENCRYPTION_KEY=c6ce8f6545bc5675d1e606614b3c4f68a268644e005793dfec4f40a7ea04f0b4

# Timezone
GENERIC_TIMEZONE=America/Sao_Paulo

# Resend (workflows que enviam e-mail: onboarding nodes manuais, Trial Ending, etc.)
RESEND_API_KEY=re_xxxxxxxx
```

> ⚠️ **IMPORTANTE:** `N8N_ENCRYPTION_KEY` não pode ser alterada após criada. Se mudar, todas as credenciais salvas no n8n são perdidas.

### 6.3 Variáveis do Django (cini-english) para o n8n

```env
N8N_ONBOARDING_WEBHOOK_ENABLED=true
N8N_ONBOARDING_WEBHOOK_URL=https://n8n-cini-english.up.railway.app/webhook/93e4033f-008d-4f18-a5e3-a0a66d784543
N8N_ONBOARDING_STATUS_TOKEN=<token secreto compartilhado>
```

### 6.4 Importar workflow no n8n Railway

1. Acessar `https://n8n-cini-english.up.railway.app`
2. Login: admin / senha configurada
3. Menu → Workflows → **Import from file**
4. Selecionar `Onboarding EducaFlowOne - PRD.json`
5. Abrir o workflow → verificar UUID do webhook no node "Webhook New User"
6. Confirmar que a URL bate com `N8N_ONBOARDING_WEBHOOK_URL` no Django
7. Toggle **Active** → ON

### 6.5 Teste de produção

```powershell
# Disparar webhook manualmente para testar (sem fazer signup real)
Invoke-WebRequest `
  -Uri "https://n8n-cini-english.up.railway.app/webhook-test/93e4033f-008d-4f18-a5e3-a0a66d784543" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{
    "event": "trial_started",
    "user_id": 1,
    "email": "jonas@teste.com",
    "first_name": "Jonas",
    "username": "jonas",
    "onboarding_check_url": "https://www.educaflowone.com.br/api/internal/onboarding/progress/",
    "onboarding_check_token": "SEU_TOKEN_AQUI"
  }'
```

> **Nota:** `/webhook-test/` funciona apenas com o workflow aberto no n8n em modo "Listen for test event". Em produção ativo, usar `/webhook/`.

---

## 7. Variáveis de Ambiente (referência completa)

### Django (Railway — cini-english)

| Variável                        | Descrição                                    |
|---------------------------------|----------------------------------------------|
| `N8N_ONBOARDING_WEBHOOK_ENABLED`| `true` para habilitar o disparo              |
| `N8N_ONBOARDING_WEBHOOK_URL`    | URL completa do webhook do n8n PRD           |
| `N8N_ONBOARDING_STATUS_TOKEN`   | Token secreto para autenticar chamadas n8n→Django |

### Evolution API (docker-compose local)

| Variável                    | Valor                          |
|-----------------------------|--------------------------------|
| `AUTHENTICATION_API_KEY`    | `minha-chave-secreta-123`      |
| `VERSION`                   | `2,3000,1035194821`            |
| `CONFIG_SESSION_PHONE_VERSION` | `2.3000.1035194821` (no .env interno) |
| `CACHE_REDIS_ENABLED`       | `true`                         |

### APIs externas

| Serviço     | Variável / Header | Onde configurar      |
|-------------|-------------------|----------------------|
| Anthropic   | `x-api-key`       | Node n8n local       |
| Resend      | `RESEND_API_KEY` (n8n env) → `Authorization: Bearer …` | Trial Ending + nodes de e-mail PRD |
| Open-Meteo  | —                 | Sem autenticação     |

---

## 8. Manutenção e Troubleshooting

### WhatsApp desconectou

```powershell
# 1. Verificar status
Invoke-WebRequest -Uri "http://localhost:8080/instance/fetchInstances" `
  -Headers @{"apikey"="minha-chave-secreta-123"} -UseBasicParsing

# 2. Reconectar (gera novo QR)
Invoke-WebRequest -Uri "http://localhost:8080/instance/connect/meu-whatsapp" `
  -Headers @{"apikey"="minha-chave-secreta-123"} -UseBasicParsing
# Salvar o base64 como PNG e escanear com o WhatsApp
```

### Evolution API não gera QR (crash loop)

A versão do Baileys pode estar desatualizada. Verificar e atualizar:

```powershell
# Buscar versão atual válida
docker run --rm --entrypoint node -w /evolution atendai/evolution-api:latest -e "
process.chdir('/evolution');
(async()=>{const {fetchLatestBaileysVersion}=require('baileys');const v=await fetchLatestBaileysVersion();console.log(v.version.join(','),v.isLatest);})();
"

# Atualizar Dockerfile.evolution com o número retornado
# Rebuildar e reiniciar
docker compose build evolution-api
docker compose down && docker compose up -d
```

### n8n Railway não está respondendo

1. Railway → serviço n8n → **Deployments** → ver logs
2. Verificar se `PORT=5678` está nas variáveis
3. Verificar conexão com Postgres-ECuC

### Workflow de onboarding não dispara

Checklist:
- [ ] `N8N_ONBOARDING_WEBHOOK_ENABLED=true` no Django (Railway)
- [ ] `N8N_ONBOARDING_WEBHOOK_URL` aponta para URL correta do n8n
- [ ] Workflow está **Active** no n8n Railway
- [ ] UUID do webhook no workflow bate com a URL configurada no Django
- [ ] Django foi redeploy após alterar as variáveis

### Email não chega (Resend)

- Verificar se o domínio `educaflowone.com.br` está verificado na Resend
- Verificar se o destinatário está na suppression list da Resend
- Verificar API key do Resend nos nodes do workflow

---

*Documentação gerada em 2026-03-19. Atualizar sempre que houver mudanças na arquitetura ou credenciais.*
