# 🚀 Guia Completo: Migração Stripe de Teste para Produção

Este documento lista **TODAS** as mudanças necessárias para migrar o sistema Stripe de modo teste para modo produção.

---

## 📋 Índice

1. [Variáveis de Ambiente](#1-variáveis-de-ambiente)
2. [Configuração no Stripe Dashboard](#2-configuração-no-stripe-dashboard)
3. [Mudanças no Código](#3-mudanças-no-código)
4. [Checklist de Migração](#4-checklist-de-migração)
5. [Testes Pós-Migração](#5-testes-pós-migração)

---

## 1. Variáveis de Ambiente

### 🔑 Chaves que PRECISAM ser alteradas no `.env`:

```bash
# ============================================
# STRIPE - MODO PRODUÇÃO
# ============================================

# ⚠️ CRÍTICO: Substituir pela Secret Key de PRODUÇÃO
# Obter em: https://dashboard.stripe.com/apikeys
# Deve começar com: sk_live_...
STRIPE_SECRET_KEY=sk_live_SUA_CHAVE_AQUI

# ⚠️ CRÍTICO: Substituir pelos Price IDs de PRODUÇÃO
# Obter após criar produtos/prices no Stripe Dashboard (modo live)
STRIPE_PRICE_ID_MONTHLY=price_XXXXX_MONTHLY_LIVE
STRIPE_PRICE_ID_SEMESTRAL=price_XXXXX_SEMESTRAL_LIVE
STRIPE_PRICE_ID_ANNUAL=price_XXXXX_ANNUAL_LIVE

# ⚠️ CRÍTICO: Substituir pelo Webhook Secret de PRODUÇÃO
# Obter após configurar webhook no Stripe Dashboard (modo live)
# Deve começar com: whsec_...
STRIPE_WEBHOOK_SECRET=whsec_SEU_WEBHOOK_SECRET_LIVE
```

### 📝 Onde obter cada chave:

1. **STRIPE_SECRET_KEY (Produção)**
   - Acesse: https://dashboard.stripe.com/apikeys
   - **IMPORTANTE**: Certifique-se de estar no modo **"Live"** (toggle no topo do dashboard)
   - Clique em "Reveal live key" na **Secret key**
   - Copie a chave que começa com `sk_live_`

2. **STRIPE_PRICE_ID_* (Produção)**
   - Veja seção [2.2 Criar Products e Prices](#22-criar-products-e-prices)

3. **STRIPE_WEBHOOK_SECRET (Produção)**
   - Veja seção [2.3 Configurar Webhook](#23-configurar-webhook)

---

## 2. Configuração no Stripe Dashboard

### 2.1 Ativar Modo Live

1. Acesse https://dashboard.stripe.com
2. No canto superior direito, há um toggle **"Test mode"** / **"Live mode"**
3. **Mude para "Live mode"** ⚠️
4. Você precisará completar a verificação da conta (se ainda não fez)

### 2.2 Criar Products e Prices (Modo Live)

⚠️ **IMPORTANTE**: Você precisa criar **NOVOS** produtos e prices no modo **Live**. Os IDs de teste não funcionam em produção.

1. Acesse https://dashboard.stripe.com/products (certifique-se de estar em **Live mode**)
2. Clique em **"+ Add product"**

#### Produto 1: Mensal
- **Name**: `EDUflow - Mensal`
- **Description**: `Assinatura mensal do EDUflow`
- **Pricing model**: `Standard pricing`
- **Price**: `R$ 49,00`
- **Billing period**: `Monthly` (recorrente)
- Clique em **"Save product"**
- **Copie o Price ID** (começa com `price_`) → Use como `STRIPE_PRICE_ID_MONTHLY`

#### Produto 2: Semestral
- **Name**: `EDUflow - Semestral`
- **Description**: `Assinatura semestral do EDUflow`
- **Pricing model**: `Standard pricing`
- **Price**: `R$ 269,00`
- **Billing period**: `Every 6 months` (recorrente)
- Clique em **"Save product"**
- **Copie o Price ID** → Use como `STRIPE_PRICE_ID_SEMESTRAL`

#### Produto 3: Anual
- **Name**: `EDUflow - Anual`
- **Description**: `Assinatura anual do EDUflow`
- **Pricing model**: `Standard pricing`
- **Price**: `R$ 479,00`
- **Billing period**: `Yearly` (recorrente)
- Clique em **"Save product"**
- **Copie o Price ID** → Use como `STRIPE_PRICE_ID_ANNUAL`

### 2.3 Configurar Webhook (Modo Live)

⚠️ **CRÍTICO**: O webhook é a única forma de o sistema saber quando um pagamento foi processado.

1. Acesse https://dashboard.stripe.com/webhooks (certifique-se de estar em **Live mode**)
2. Clique em **"+ Add endpoint"**
3. **Endpoint URL**: `https://seudominio.com/api/webhooks/stripe/`
   - ⚠️ Substitua `seudominio.com` pelo seu domínio real
   - Exemplo: `https://eduflow.com.br/api/webhooks/stripe/`
4. **Description**: `EDUflow - Webhook de Produção`
5. **Events to send**: Selecione os seguintes eventos:
   - ✅ `checkout.session.completed` ⭐ **ESSENCIAL**
   - ✅ `customer.subscription.created` ⭐ **ESSENCIAL**
   - ✅ `invoice.paid` ⭐ **ESSENCIAL**
   - ✅ `invoice.payment_succeeded` ⭐ **ESSENCIAL**
   - ✅ `invoice.payment_failed`
   - ✅ `customer.subscription.deleted`
   - ✅ `customer.subscription.updated`
6. Clique em **"Add endpoint"**
7. **Copie o "Signing secret"** (começa com `whsec_`) → Use como `STRIPE_WEBHOOK_SECRET`

### 2.4 Verificar Configurações de Conta

1. Acesse https://dashboard.stripe.com/settings/account
2. Verifique se:
   - ✅ Conta está verificada
   - ✅ Informações de negócio estão completas
   - ✅ Dados bancários estão configurados (para receber pagamentos)

---

## 3. Mudanças no Código

### 3.1 Nenhuma mudança necessária! ✅

O código atual já está preparado para produção. Ele usa variáveis de ambiente, então basta atualizar o `.env`.

**Arquivos que usam Stripe (já estão corretos):**
- `core/views.py` - Usa `os.environ.get("STRIPE_SECRET_KEY")` e `os.environ.get("STRIPE_WEBHOOK_SECRET")`
- `core/views.py` - Usa `os.environ.get("STRIPE_PRICE_ID_MONTHLY")`, etc.

### 3.2 Verificações Recomendadas (Opcional)

Se quiser adicionar validações extras, você pode:

#### Opção A: Adicionar validação de ambiente

Em `core/views.py`, após a linha 659, adicione:

```python
# Validação de ambiente (opcional)
if not stripe.api_key:
    raise ValueError("STRIPE_SECRET_KEY não configurada no ambiente")
if not stripe.api_key.startswith(('sk_test_', 'sk_live_')):
    raise ValueError("STRIPE_SECRET_KEY inválida")
```

#### Opção B: Logging diferenciado por ambiente

```python
import logging
logger = logging.getLogger(__name__)

# No início de create_checkout_session:
is_live = stripe.api_key.startswith('sk_live_')
logger.info(f"Criando checkout session em modo {'PRODUÇÃO' if is_live else 'TESTE'}")
```

---

## 4. Checklist de Migração

Use este checklist para garantir que nada foi esquecido:

### Pré-Migração
- [ ] Conta Stripe verificada e ativa
- [ ] Dados bancários configurados no Stripe
- [ ] Domínio de produção configurado e funcionando
- [ ] SSL/HTTPS configurado no domínio

### Configuração Stripe Dashboard
- [ ] Modo Live ativado no Stripe Dashboard
- [ ] 3 produtos criados no modo Live (Mensal, Semestral, Anual)
- [ ] 3 Price IDs copiados dos produtos Live
- [ ] Webhook configurado no modo Live
- [ ] Webhook Secret copiado
- [ ] Eventos do webhook configurados corretamente

### Variáveis de Ambiente
- [ ] `STRIPE_SECRET_KEY` atualizada para chave Live (`sk_live_...`)
- [ ] `STRIPE_PRICE_ID_MONTHLY` atualizado com Price ID Live
- [ ] `STRIPE_PRICE_ID_SEMESTRAL` atualizado com Price ID Live
- [ ] `STRIPE_PRICE_ID_ANNUAL` atualizado com Price ID Live
- [ ] `STRIPE_WEBHOOK_SECRET` atualizado com Webhook Secret Live
- [ ] Variáveis de ambiente carregadas no servidor de produção

### Código
- [ ] Código deployado no servidor de produção
- [ ] Servidor reiniciado após atualizar variáveis de ambiente

### Testes
- [ ] Teste de checkout com cartão real (valor mínimo)
- [ ] Verificação de webhook recebido
- [ ] Verificação de assinatura ativada no banco de dados
- [ ] Teste de cancelamento via Customer Portal
- [ ] Verificação de logs de erro

---

## 5. Testes Pós-Migração

### 5.1 Teste de Checkout

1. Acesse a landing page em produção
2. Clique em um plano
3. Complete o cadastro
4. Será redirecionado para Stripe Checkout (modo Live)
5. Use um **cartão de teste real** (ou cartão real com valor mínimo)
6. Complete o pagamento
7. Verifique se foi redirecionado para `/payment-processing/`

### 5.2 Verificar Webhook

1. Acesse https://dashboard.stripe.com/webhooks (modo Live)
2. Clique no webhook configurado
3. Veja a aba **"Events"**
4. Verifique se os eventos estão sendo recebidos:
   - `checkout.session.completed`
   - `invoice.paid`
   - `customer.subscription.created`

### 5.3 Verificar Banco de Dados

1. Acesse o admin Django ou banco de dados
2. Verifique a tabela `core_subscription`:
   - Deve ter uma nova assinatura com `status='active'`
   - Deve ter `stripe_customer_id` preenchido
   - Deve ter `stripe_subscription_id` preenchido
3. Verifique a tabela `core_stripeevent`:
   - Deve ter eventos registrados
   - Deve ter `processed=True`

### 5.4 Teste de Cancelamento

1. Acesse `/planos/` (tela de planos)
2. Clique em "Gerenciar assinatura"
3. Deve abrir o Stripe Customer Portal
4. Teste o cancelamento
5. Verifique se a assinatura foi atualizada no banco

---

## 6. Troubleshooting

### Problema: Webhook não está sendo chamado

**Soluções:**
1. Verifique se a URL do webhook está correta no Stripe Dashboard
2. Verifique se o domínio tem SSL/HTTPS válido
3. Verifique os logs do servidor para erros
4. Teste a URL manualmente: `curl https://seudominio.com/api/webhooks/stripe/`
5. Verifique se o webhook está no modo **Live** (não Test)

### Problema: Assinatura não está sendo ativada

**Soluções:**
1. Verifique se o webhook está processando `invoice.paid`
2. Verifique a tabela `core_stripeevent` para erros
3. Verifique os logs do servidor
4. Confirme que `STRIPE_WEBHOOK_SECRET` está correto

### Problema: Checkout Session não é criada

**Soluções:**
1. Verifique se `STRIPE_SECRET_KEY` está configurada (modo Live)
2. Confirme que os Price IDs estão corretos (modo Live)
3. Verifique logs do servidor
4. Teste a API diretamente: `POST /api/subscription/create-checkout/`

### Problema: Erro "Invalid API Key"

**Soluções:**
1. Certifique-se de estar usando a chave **Live** (`sk_live_...`)
2. Verifique se não há espaços extras na chave
3. Verifique se a chave está no arquivo `.env` correto
4. Reinicie o servidor após atualizar o `.env`

---

## 7. Segurança em Produção

### ✅ Boas Práticas Implementadas

- ✅ Webhook secret usado para verificar assinaturas
- ✅ Idempotência de eventos (tabela `StripeEvent`)
- ✅ Metadata em todos os objetos Stripe
- ✅ `client_reference_id` ligando checkout ao usuário

### ⚠️ Recomendações Adicionais

1. **Nunca commite o `.env` no Git**
   - Certifique-se de que `.env` está no `.gitignore`
   
2. **Use variáveis de ambiente do servidor**
   - No Railway, Heroku, etc., configure as variáveis diretamente no painel
   - Não use arquivo `.env` em produção

3. **Monitore logs de erro**
   - Configure alertas para erros de webhook
   - Monitore a tabela `StripeEvent` para eventos não processados

4. **Backup regular**
   - Faça backup da tabela `core_subscription` regularmente

---

## 8. Resumo das Mudanças

### O que MUDAR:
1. ✅ Variáveis de ambiente (`.env` ou variáveis do servidor)
2. ✅ Configuração no Stripe Dashboard (produtos, prices, webhook)

### O que NÃO mudar:
1. ❌ Código Python (já está preparado)
2. ❌ Estrutura do banco de dados
3. ❌ URLs e endpoints

---

## 9. Suporte

Se encontrar problemas durante a migração:

1. Verifique os logs do servidor
2. Verifique os eventos no Stripe Dashboard
3. Verifique a tabela `core_stripeevent` para erros
4. Consulte a documentação do Stripe: https://stripe.com/docs

---

**Última atualização**: Janeiro 2026
**Versão**: 1.0
