# Correção do Webhook Stripe

## Resumo do problema

O Stripe está enviando eventos para uma URL **antiga e incorreta** (Railway antigo + path errado). O app principal agora é **www.educaflowone.com.br**:

| Configurado no Stripe (errado) | URL correta no seu app |
|--------------------------------|------------------------|
| `https://cini-english-cini-english.up.railway.app/stripe/webhook/` | `https://www.educaflowone.com.br/api/webhooks/stripe/` |

**Tipos de erro:**
- **116 requisições**: "could not connect" — app pode estar dormindo (Railway free tier)
- **41 requisições**: HTTP 404 — a URL `/stripe/webhook/` não existe no seu Django

---

## Passo 1: Corrigir a URL no Stripe Dashboard

1. Acesse https://dashboard.stripe.com/webhooks (certifique-se de estar em **Live mode**)
2. Clique no webhook que mostra a URL com erro
3. Clique em **"Update details"** ou no ícone de edição
4. Altere a **Endpoint URL** para:
   ```
   https://www.educaflowone.com.br/api/webhooks/stripe/
   ```
5. Salve as alterações

---

## Passo 2: Conferir variáveis no Railway

No painel do Railway, confira as variáveis:

- `STRIPE_WEBHOOK_SECRET` — deve ser o secret do webhook de **produção** (começa com `whsec_`)
- `STRIPE_SECRET_KEY` — chave de produção (`sk_live_...`)

O `STRIPE_WEBHOOK_SECRET` de **produção** é diferente do de teste. Ao criar/editar o webhook no Stripe Dashboard, use o secret que aparece na tela de detalhes do endpoint.

---

## Passo 3 (opcional): Evitar “could not connect” no Railway

Os 116 erros de conexão costumam ocorrer quando o app dorme (plano Free/Hobby no Railway).

### Opção A: UptimeRobot ou similar (grátis)
- Crie conta em https://uptimerobot.com
- Configure um monitor HTTP que acesse `https://www.educaflowone.com.br/` a cada 5 minutos
- O Railway mantém o app acordado com esse ping

### Opção B: Upgrade no Railway
- Planos pagos evitam o modo “dormir” em ambiente de produção

---

## Passo 4: Testar o webhook

Depois de corrigir a URL:

1. No Stripe Dashboard, vá em **Webhooks** → seu endpoint
2. Clique em **"Send test webhook"**
3. Escolha o evento `checkout.session.completed` ou `invoice.paid`
4. Clique em **"Send test webhook"**

Deve aparecer status **200** (sucesso) nos logs do Stripe.

---

## Prazo

O Stripe informou que vai **parar de tentar** enviar para o endpoint com erro em **26 de fevereiro de 2026**. Depois disso, nenhum evento será entregue até a URL ser corrigida, então é importante aplicar as mudanças o quanto antes.
