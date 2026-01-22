# ✅ Checklist Final - Pré-Deploy Railway

Use este checklist para garantir que **TUDO** está pronto antes do deploy.

---

## 🔑 Variáveis de Ambiente no Railway

Verifique se estas **5 variáveis Stripe** estão configuradas:

- [ ] `STRIPE_SECRET_KEY` = `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`
- [ ] `STRIPE_PRICE_ID_MONTHLY` = `price_1SsS5y07a2dTSXAiwRUOeJKg`
- [ ] `STRIPE_PRICE_ID_SEMESTRAL` = `price_1SsS6307a2dTSXAi18ymSjQf`
- [ ] `STRIPE_PRICE_ID_ANNUAL` = `price_1SsS6707a2dTSXAixIzBjfXF`
- [ ] `STRIPE_WEBHOOK_SECRET` = `whsec_6EDpTlc21QpBRg397D96g0Rfkv4pbiYk`

### ⚠️ Outras Variáveis Importantes (Verificar se já existem)

O Railway geralmente configura automaticamente, mas verifique:

- [ ] `DATABASE_URL` - Configurado automaticamente pelo Railway (PostgreSQL)
- [ ] `DJANGO_SECRET_KEY` - Se não existir, o sistema usa um fallback (não recomendado para produção)
- [ ] `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT` - Se usar configuração manual do banco

**Recomendação**: Se `DATABASE_URL` não estiver configurado, o Railway geralmente cria automaticamente quando você adiciona um serviço PostgreSQL. Se já tem um banco configurado, está ok.

---

## 🌐 Webhook no Stripe Dashboard

⚠️ **CRÍTICO**: Atualize o webhook **ANTES** ou **DEPOIS** do deploy (mas precisa estar correto para funcionar):

- [ ] Acesse https://dashboard.stripe.com/webhooks (modo **Live**)
- [ ] Clique no webhook de produção
- [ ] Atualize a **Endpoint URL** para: `https://SEU-DOMINIO-RAILWAY.app/api/webhooks/stripe/`
  - ⚠️ **IMPORTANTE**: Você precisa saber qual é a URL do seu app no Railway
  - Para descobrir: Railway → Seu Serviço → Aba "Settings" → "Domains"
  - Exemplo: `https://eduflow-production.up.railway.app/api/webhooks/stripe/`
- [ ] Salve as alterações

**Nota**: Se você ainda não sabe a URL do Railway, pode fazer o deploy primeiro e depois atualizar o webhook. Mas o webhook só funcionará após ser atualizado.

---

## 🔒 Configurações de Segurança (Opcional mas Recomendado)

### Opção 1: Usar Variáveis de Ambiente (Recomendado)

Adicione estas variáveis no Railway para melhor segurança:

- [ ] `DEBUG` = `False` (em produção)
- [ ] `DJANGO_SECRET_KEY` = (uma chave secreta forte, se ainda não tiver)

**Como gerar DJANGO_SECRET_KEY**:
```python
# Execute no Python:
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Opção 2: Deixar como está (Funciona, mas menos seguro)

O código atual tem:
- `DEBUG = True` (mostra erros detalhados - útil para debug, mas expõe informações)
- `ALLOWED_HOSTS = ["*"]` (aceita qualquer host - ok para Railway)
- `SECRET_KEY` com fallback (funciona, mas não é ideal)

**Recomendação**: Para produção real, configure `DEBUG=False` via variável de ambiente.

---

## 📦 Verificações de Código

- [ ] Código commitado e pushado para o repositório
- [ ] Nenhum arquivo `.env` com chaves de produção no Git
- [ ] `.gitignore` contém `.env`

---

## 🚀 Deploy

### Passo 1: Fazer Deploy

1. No Railway, vá para o seu serviço
2. Se tiver integração com Git:
   - Faça push das alterações
   - O Railway fará deploy automático
3. Se não tiver integração:
   - Clique em **"Deploy"** ou **"Redeploy"**

### Passo 2: Verificar Logs

1. Após o deploy iniciar, clique na aba **"Deployments"**
2. Clique no deploy mais recente
3. Veja os logs e verifique:
   - ✅ "Starting server..."
   - ✅ "Application startup complete"
   - ✅ Nenhum erro relacionado a Stripe
   - ❌ Se houver erros, verifique as variáveis de ambiente

### Passo 3: Testar Aplicação

1. Acesse a URL do seu app no Railway
2. Verifique se a landing page carrega
3. Teste login/signup
4. Verifique se não há erros no console do navegador

---

## 🧪 Teste Stripe (Após Deploy)

### 1. Teste de Checkout

1. Acesse a landing page
2. Clique em um plano
3. Complete o cadastro
4. Deve redirecionar para Stripe Checkout (modo Live)
5. Use um cartão de teste real ou cartão real com valor mínimo
6. Complete o pagamento
7. Verifique redirecionamento para `/payment-processing/`

### 2. Verificar Webhook

1. Acesse https://dashboard.stripe.com/webhooks (modo Live)
2. Clique no webhook
3. Veja a aba **"Events"**
4. Deve aparecer eventos:
   - `checkout.session.completed`
   - `invoice.paid`
   - `customer.subscription.created`

### 3. Verificar Banco de Dados

1. Acesse o admin Django ou banco do Railway
2. Verifique `core_subscription`:
   - Nova assinatura com `status='active'`
   - `stripe_customer_id` preenchido
   - `stripe_subscription_id` preenchido

---

## ✅ Resumo: O que você JÁ FEZ

- ✅ Coletou todas as chaves Stripe de produção
- ✅ Criou produtos/prices no Stripe Dashboard (modo Live)
- ✅ Configurou webhook no Stripe Dashboard (modo Live)
- ✅ Adicionou variáveis de ambiente no Railway

## ⚠️ O que FALTA (se ainda não fez)

- [ ] Atualizar URL do webhook no Stripe com a URL do Railway
- [ ] (Opcional) Configurar `DEBUG=False` no Railway
- [ ] (Opcional) Configurar `DJANGO_SECRET_KEY` no Railway
- [ ] Fazer deploy
- [ ] Testar checkout em produção

---

## 🎯 Pode Fazer Deploy?

**SIM, pode fazer deploy!** ✅

As variáveis Stripe estão configuradas. O único passo que pode ser feito antes ou depois é atualizar a URL do webhook no Stripe Dashboard (mas precisa ser feito para o webhook funcionar).

**Ordem recomendada:**
1. ✅ Fazer deploy agora
2. ✅ Obter a URL do Railway após o deploy
3. ✅ Atualizar webhook no Stripe Dashboard com a URL correta
4. ✅ Testar checkout

---

## 🚨 Se algo der errado

1. Verifique os logs do Railway
2. Verifique se todas as variáveis estão corretas
3. Verifique se o webhook está apontando para a URL correta
4. Teste a URL do webhook manualmente: `curl https://seu-dominio-railway.app/api/webhooks/stripe/`

---

**Última atualização**: Janeiro 2026
