# 🚂 Guia Completo: Deploy Stripe Produção no Railway

Este guia mostra **exatamente** como configurar todas as variáveis de ambiente no Railway e preparar o sistema para produção.

---

## ✅ Dados Coletados (Verificação)

Você já coletou todos os dados necessários:

- ✅ **STRIPE_SECRET_KEY**: `sk_live_...` (sua chave de produção)
- ✅ **STRIPE_PRICE_ID_MONTHLY**: `price_XXXXX` (seu Price ID mensal)
- ✅ **STRIPE_PRICE_ID_SEMESTRAL**: `price_XXXXX` (seu Price ID semestral)
- ✅ **STRIPE_PRICE_ID_ANNUAL**: `price_XXXXX` (seu Price ID anual)
- ✅ **STRIPE_WEBHOOK_SECRET**: `whsec_XXXXX` (seu Webhook Secret)

**Nota sobre o link de billing**: O link `https://billing.stripe.com/p/login/...` é apenas para você acessar o painel de billing do Stripe. O sistema cria o portal dinamicamente via API, então não precisa ser configurado.

---

## 📋 Passo 1: Configurar Variáveis no Railway

### 1.1 Acessar o Railway Dashboard

1. Acesse https://railway.app
2. Faça login na sua conta
3. Selecione o projeto do EDUflow

### 1.2 Adicionar Variáveis de Ambiente

1. No projeto, clique no **serviço** (service) do seu app Django
2. Clique na aba **"Variables"** (ou "Variáveis")
3. Clique em **"+ New Variable"** (ou "+ Nova Variável")

### 1.3 Adicionar Cada Variável

Adicione as seguintes variáveis **uma por uma**:

#### Variável 1: STRIPE_SECRET_KEY
- **Name**: `STRIPE_SECRET_KEY`
- **Value**: `sk_live_SUA_CHAVE_AQUI` (substitua pela sua chave de produção)
- Clique em **"Add"**

#### Variável 2: STRIPE_PRICE_ID_MONTHLY
- **Name**: `STRIPE_PRICE_ID_MONTHLY`
- **Value**: `price_XXXXX` (substitua pelo seu Price ID mensal de produção)
- Clique em **"Add"**

#### Variável 3: STRIPE_PRICE_ID_SEMESTRAL
- **Name**: `STRIPE_PRICE_ID_SEMESTRAL`
- **Value**: `price_XXXXX` (substitua pelo seu Price ID semestral de produção)
- Clique em **"Add"**

#### Variável 4: STRIPE_PRICE_ID_ANNUAL
- **Name**: `STRIPE_PRICE_ID_ANNUAL`
- **Value**: `price_XXXXX` (substitua pelo seu Price ID anual de produção)
- Clique em **"Add"**

#### Variável 5: STRIPE_WEBHOOK_SECRET
- **Name**: `STRIPE_WEBHOOK_SECRET`
- **Value**: `whsec_XXXXX` (substitua pelo seu Webhook Secret de produção)
- Clique em **"Add"**

### 1.4 Verificar Variáveis

Após adicionar todas, você deve ver estas 5 variáveis na lista:
- ✅ `STRIPE_SECRET_KEY`
- ✅ `STRIPE_PRICE_ID_MONTHLY`
- ✅ `STRIPE_PRICE_ID_SEMESTRAL`
- ✅ `STRIPE_PRICE_ID_ANNUAL`
- ✅ `STRIPE_WEBHOOK_SECRET`

---

## 📋 Passo 2: Atualizar Webhook no Stripe Dashboard

⚠️ **IMPORTANTE**: O webhook precisa apontar para a URL de produção do Railway.

### 2.1 Obter URL do Railway

1. No Railway, vá para o seu serviço
2. Clique na aba **"Settings"**
3. Procure por **"Domains"** ou **"Custom Domain"**
4. Copie a URL do seu app (exemplo: `https://eduflow-production.up.railway.app`)

### 2.2 Atualizar Webhook no Stripe

1. Acesse https://dashboard.stripe.com/webhooks (certifique-se de estar em **Live mode**)
2. Clique no webhook que você criou
3. Clique em **"Edit"** ou **"Update endpoint"**
4. Atualize a **Endpoint URL** para: `https://SEU-DOMINIO-RAILWAY.app/api/webhooks/stripe/`
   - Exemplo: `https://eduflow-production.up.railway.app/api/webhooks/stripe/`
5. Clique em **"Save"**

---

## 📋 Passo 3: Atualizar .env Local (Opcional)

Se você ainda usa `.env` localmente para desenvolvimento, atualize com os valores de **TESTE** (não produção):

```bash
# ============================================
# STRIPE - MODO TESTE (para desenvolvimento local)
# ============================================
STRIPE_SECRET_KEY=sk_test_SUA_CHAVE_TESTE_AQUI
STRIPE_PRICE_ID_MONTHLY=price_1Ss5v607a2dTSXAiGpSQsB2z
STRIPE_PRICE_ID_SEMESTRAL=price_1Ss74807a2dTSXAirvGII1M1
STRIPE_PRICE_ID_ANNUAL=price_1Ss78O07a2dTSXAizRirj0Qn
STRIPE_WEBHOOK_SECRET=whsec_c7c5905d7f6dddd3ef83eea9086ccad037ea96b31037e4d322f065690b1df981
```

⚠️ **IMPORTANTE**: 
- Use chaves de **TESTE** no `.env` local
- Use chaves de **PRODUÇÃO** apenas no Railway
- **NUNCA** commite o `.env` com chaves de produção no Git

---

## 📋 Passo 4: Verificar Código (Já Está Correto!)

O código já está preparado e não precisa de mudanças. Ele usa:

- ✅ `os.environ.get("STRIPE_SECRET_KEY")` - Linha 659 de `core/views.py`
- ✅ `os.environ.get("STRIPE_PRICE_ID_MONTHLY")` - Linha 681
- ✅ `os.environ.get("STRIPE_PRICE_ID_SEMESTRAL")` - Linha 682
- ✅ `os.environ.get("STRIPE_PRICE_ID_ANNUAL")` - Linha 683
- ✅ `os.environ.get("STRIPE_WEBHOOK_SECRET")` - Linha 781

**Nenhuma alteração no código é necessária!** ✅

---

## 📋 Passo 5: Deploy no Railway

### 5.1 Fazer Deploy

1. No Railway, vá para o seu serviço
2. Clique em **"Deploy"** ou aguarde o deploy automático (se configurado)
3. Aguarde o deploy completar

### 5.2 Verificar Logs

1. Clique na aba **"Deployments"**
2. Clique no deploy mais recente
3. Verifique os logs para garantir que não há erros
4. Procure por mensagens como:
   - ✅ "Starting server..."
   - ✅ "Application startup complete"
   - ❌ Se houver erros, verifique as variáveis de ambiente

---

## 📋 Passo 6: Testar em Produção

### 6.1 Teste de Checkout

1. Acesse sua landing page em produção
2. Clique em um plano
3. Complete o cadastro
4. Será redirecionado para Stripe Checkout (modo Live)
5. Use um **cartão de teste real** ou cartão real com valor mínimo
6. Complete o pagamento
7. Verifique se foi redirecionado para `/payment-processing/`

### 6.2 Verificar Webhook

1. Acesse https://dashboard.stripe.com/webhooks (modo Live)
2. Clique no webhook configurado
3. Veja a aba **"Events"**
4. Verifique se os eventos estão sendo recebidos:
   - `checkout.session.completed`
   - `invoice.paid`
   - `customer.subscription.created`

### 6.3 Verificar Banco de Dados

1. Acesse o admin Django ou banco de dados do Railway
2. Verifique a tabela `core_subscription`:
   - Deve ter uma nova assinatura com `status='active'`
   - Deve ter `stripe_customer_id` preenchido
   - Deve ter `stripe_subscription_id` preenchido

---

## 🔍 Checklist Final

Antes de considerar o deploy completo, verifique:

- [ ] Todas as 5 variáveis configuradas no Railway
- [ ] Webhook atualizado com URL de produção do Railway
- [ ] Deploy realizado com sucesso
- [ ] Teste de checkout funcionando
- [ ] Webhook recebendo eventos
- [ ] Assinatura sendo ativada no banco de dados
- [ ] Customer Portal funcionando (botão "Gerenciar assinatura" em `/planos/`)

---

## 🚨 Troubleshooting

### Problema: Variáveis não estão sendo carregadas

**Solução:**
1. Verifique se as variáveis estão no Railway (aba "Variables")
2. Reinicie o serviço no Railway
3. Verifique os logs do deploy

### Problema: Webhook não está sendo chamado

**Soluções:**
1. Verifique se a URL do webhook está correta (deve ser a URL do Railway)
2. Verifique se o domínio tem SSL/HTTPS válido
3. Teste a URL manualmente: `curl https://seu-dominio-railway.app/api/webhooks/stripe/`
4. Verifique os logs do Railway para erros

### Problema: Erro "Invalid API Key"

**Soluções:**
1. Verifique se `STRIPE_SECRET_KEY` está correta no Railway
2. Certifique-se de que está usando a chave **Live** (`sk_live_...`)
3. Verifique se não há espaços extras na chave
4. Reinicie o serviço após atualizar variáveis

---

## 📝 Resumo das Variáveis no Railway

```bash
STRIPE_SECRET_KEY=sk_live_SUA_CHAVE_AQUI
STRIPE_PRICE_ID_MONTHLY=price_XXXXX
STRIPE_PRICE_ID_SEMESTRAL=price_XXXXX
STRIPE_PRICE_ID_ANNUAL=price_XXXXX
STRIPE_WEBHOOK_SECRET=whsec_XXXXX
```

---

## ✅ Pronto!

Após seguir todos os passos, seu sistema Stripe estará funcionando em produção no Railway!

**Última atualização**: Janeiro 2026
