# Configuração do Fluxo de Assinatura Stripe

## ⚙️ Configuração Rápida - Arquivo `.env`

### ⚠️ IMPORTANTE: Obter a Secret Key Correta

A chave `mk_1Psmxe07a2dTSXAimAm2329e` **NÃO é uma Secret Key válida**. Para criar checkout sessions, você precisa de uma **Secret Key** que começa com:
- `sk_test_` para ambiente de **teste**
- `sk_live_` para ambiente de **produção**

**Como obter a Secret Key correta:**
1. Acesse https://dashboard.stripe.com/test/apikeys (para teste) ou https://dashboard.stripe.com/apikeys (para produção)
2. Procure por **"Secret key"** (não "Publishable key" ou "Restricted key")
3. A chave deve começar com `sk_test_` ou `sk_live_`
4. Clique em "Reveal test key" ou "Reveal live key" para ver a chave completa
5. Copie a chave e adicione no `.env`

**Copie e cole estas linhas no seu arquivo `.env` (na raiz do projeto):**

```bash
STRIPE_SECRET_KEY=sk_test_...  # ⚠️ SUBSTITUA pela sua Secret Key real (deve começar com sk_test_ ou sk_live_)

# Stripe Product IDs (modo teste)
STRIPE_PRODUCT_ID_MONTHLY=prod_TplRr6Bjq9XFCI
STRIPE_PRODUCT_ID_SEMESTRAL=prod_TpmdcPOQrhlk15
STRIPE_PRODUCT_ID_ANNUAL=prod_TpmhnzQMu2KxeC

# Stripe Price IDs (modo teste)
STRIPE_PRICE_ID_MONTHLY=price_1Ss5v607a2dTSXAiGpSQsB2z
STRIPE_PRICE_ID_SEMESTRAL=price_1Ss74807a2dTSXAirvGII1M1
STRIPE_PRICE_ID_ANNUAL=price_1Ss78O07a2dTSXAizRirj0Qn

# Webhook Secret (teste local - atualizar quando configurar webhook em produção)
STRIPE_WEBHOOK_SECRET=whsec_c7c5905d7f6dddd3ef83eea9086ccad037ea96b31037e4d322f065690b1df981
```

**⚠️ Importante**: 
- O `STRIPE_WEBHOOK_SECRET` acima é o secret gerado pelo `stripe listen` para testes locais. Quando você configurar o webhook em produção no Stripe Dashboard, precisará usar o secret de produção (que será diferente).
- A `STRIPE_SECRET_KEY` deve ser uma **Secret Key** (começa com `sk_test_` ou `sk_live_`), não uma restricted key ou publishable key.

**Status atual (modo teste):**
- ✅ Product ID Mensal: `prod_TplRr6Bjq9XFCI`
- ✅ Product ID Semestral: `prod_TpmdcPOQrhlk15`
- ✅ Product ID Anual: `prod_TpmhnzQMu2KxeC`
- ✅ Price ID Mensal: `price_1Ss5v607a2dTSXAiGpSQsB2z`
- ✅ Price ID Semestral: `price_1Ss74807a2dTSXAirvGII1M1`
- ✅ Price ID Anual: `price_1Ss78O07a2dTSXAizRirj0Qn`
- ✅ Webhook Secret (teste local): `whsec_c7c5905d7f6dddd3ef83eea9086ccad037ea96b31037e4d322f065690b1df981`

⚠️ **Nota**: Todos os IDs acima são do modo **teste**. Quando for para produção, você precisará criar novos produtos e prices no Stripe Dashboard e atualizar essas variáveis.

---

## Visão Geral do Fluxo

O novo fluxo SaaS implementado segue o padrão profissional:

1. **Landing Page** → Usuário escolhe plano (mensal/semestral/anual)
2. **Signup** (`/signup?plan=X`) → Usuário cria conta
3. **Checkout Session** → Backend cria sessão Stripe e redireciona
4. **Stripe Checkout** → Usuário completa pagamento
5. **Payment Processing** (`/payment-processing`) → Tela de "processando"
6. **Webhook** → Stripe envia eventos (única fonte de verdade)
7. **Ativação** → Sistema ativa acesso após `invoice.paid`

## Variáveis de Ambiente Necessárias

### O que colocar no arquivo `.env`:

Adicione estas linhas ao seu arquivo `.env` (na raiz do projeto):

```bash
# Stripe API Keys
STRIPE_SECRET_KEY=mk_1Psmxe07a2dTSXAimAm2329e
STRIPE_WEBHOOK_SECRET=whsec_c7c5905d7f6dddd3ef83eea9086ccad037ea96b31037e4d322f065690b1df981  # Obter no Stripe Dashboard (seção Webhooks)

# Stripe Product and Price IDs
STRIPE_PRODUCT_ID=prod_TplRr6Bjq9XFCI
STRIPE_PRICE_ID_MONTHLY=price_1Ss5v607a2dTSXAiGpSQsB2z
STRIPE_PRICE_ID_SEMESTRAL=price_...  # Adicionar quando criar o plano semestral
STRIPE_PRICE_ID_ANNUAL=price_...  # Adicionar quando criar o plano anual
```

**Importante**: 
- Todos os IDs acima são do modo **teste** do Stripe
- Quando for para produção, você precisará criar novos produtos e prices no Stripe Dashboard
- O `STRIPE_WEBHOOK_SECRET` para testes locais está configurado acima. Para produção, você obtém após configurar o webhook no Stripe Dashboard (veja seção abaixo)

## Configuração no Stripe Dashboard

### 1. Criar Products e Prices

1. Acesse https://dashboard.stripe.com/products
2. Crie 3 produtos:
   - **Mensal**: R$ 49/mês (recurring monthly)
   - **Semestral**: R$ 269/6 meses (recurring every 6 months)
   - **Anual**: R$ 479/ano (recurring yearly)
3. Copie os **Price IDs** e adicione às variáveis de ambiente

### 2. Configurar Webhook

1. Acesse https://dashboard.stripe.com/webhooks
2. Clique em "Add endpoint"
3. URL: `https://seudominio.com/api/webhooks/stripe/`
4. Eventos para escutar:
   - `checkout.session.completed` ⭐ **IMPORTANTE**: Ativa assinatura imediatamente após checkout
   - `customer.subscription.created` ⭐ Ativa assinatura quando criada
   - `invoice.paid` - Confirma pagamento de invoice
   - `invoice.payment_failed` - Processa falha de pagamento
   - `customer.subscription.deleted` - Processa cancelamento
   - `customer.subscription.updated` - Atualiza status da assinatura
5. Copie o **Signing secret** e adicione como `STRIPE_WEBHOOK_SECRET`

### 3. Testar com Stripe CLI (Opcional)

#### Instalação do Stripe CLI no Windows

**Opção 1: Usando Scoop (Recomendado)**
```powershell
# Instalar Scoop (se ainda não tiver)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex

# Instalar Stripe CLI
scoop install stripe
```

**Opção 2: Download Manual**
1. Acesse https://github.com/stripe/stripe-cli/releases/latest
2. Baixe o arquivo `stripe_X.X.X_windows_x86_64.zip`
3. Extraia o arquivo `stripe.exe`
4. Adicione ao PATH ou coloque na pasta do projeto

**Opção 3: Usando Chocolatey**
```powershell
choco install stripe-cli
```

#### Usar o Stripe CLI

**1. Fazer login (já feito ✅)**
```powershell
stripe login
```
Você verá uma mensagem como:
```
Done! The Stripe CLI is configured for [SUA EMPRESA] with account id acct_...
Please note: this key will expire after 90 days, at which point you'll need to re-authenticate.
```

**2. Testar webhooks localmente**

Em um terminal separado, inicie seu servidor Django:
```powershell
python manage.py runserver
```

Em outro terminal, execute:
```powershell
stripe listen --forward-to http://127.0.0.1:8000/api/webhooks/stripe/
```

**Importante**: 
- O comando `stripe listen` mostrará um **webhook signing secret** (começa com `whsec_`)
- **Copie esse secret** e adicione no seu `.env` como `STRIPE_WEBHOOK_SECRET` para testes locais
- Mantenha esse terminal aberto enquanto testa os pagamentos
- A chave de autenticação expira em 90 dias - você precisará fazer `stripe login` novamente quando isso acontecer

## Migrations

Execute as migrations para criar as tabelas:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Estrutura das Tabelas

### Subscription
- `user`: OneToOne com User
- `plan`: monthly, semestral, annual
- `status`: active, pending, canceled, past_due, unpaid
- `stripe_customer_id`: ID do cliente no Stripe
- `stripe_subscription_id`: ID da assinatura no Stripe
- `current_period_start/end`: Período atual da assinatura

### StripeEvent
- `event_id`: ID único do evento (para idempotência)
- `event_type`: Tipo do evento
- `processed`: Se já foi processado
- `event_data`: JSON completo do evento

## Endpoints Criados

### Públicos
- `POST /api/auth/signup/` - Criar conta
- `POST /api/webhooks/stripe/` - Webhook do Stripe

### Autenticados
- `POST /api/subscription/create-checkout/` - Criar checkout session
- `GET /api/subscription/status/` - Status da assinatura

## Telas Criadas

- `/signup/?plan=X` - Tela de cadastro com plano
- `/payment-processing/` - Tela de "pagamento em processamento"

## Boas Práticas Implementadas

✅ **Idempotência de Webhook**: Tabela `StripeEvent` previne processamento duplicado  
✅ **Webhook como fonte de verdade**: Acesso só é ativado via webhook  
✅ **client_reference_id**: Liga checkout session ao usuário  
✅ **Metadata**: Armazena user_id e plan em todos os objetos Stripe  
✅ **Não confia em success_url**: Apenas webhook ativa acesso  

## Testando

1. Acesse `/landing/`
2. Clique em um plano
3. Preencha o cadastro em `/signup`
4. Será redirecionado para Stripe Checkout
5. Use cartão de teste: `4242 4242 4242 4242`
6. Após pagamento, webhook ativa acesso

## Troubleshooting

### Webhook não está sendo chamado
- Verifique se a URL está correta no Stripe Dashboard
- Teste com Stripe CLI localmente
- Verifique logs do servidor

### Assinatura não está sendo ativada
- Verifique se o webhook está processando `invoice.paid`
- Verifique logs em `StripeEvent` (campo `error_message`)
- Confirme que `STRIPE_WEBHOOK_SECRET` está correto

### Checkout Session não é criada
- Verifique se `STRIPE_SECRET_KEY` está configurado
- Confirme que os Price IDs estão corretos
- Verifique logs do backend
