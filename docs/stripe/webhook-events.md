# Eventos do Webhook Stripe

Para que todos os emails automáticos funcionem, o webhook precisa estar configurado com estes eventos:

## Eventos obrigatórios

| Evento | Uso |
|--------|-----|
| `checkout.session.completed` | Email "Assinatura ativada" |
| `invoice.payment_failed` | Email "Pagamento falhou" |
| `customer.subscription.updated` | Email "Cancelamento agendado" |
| `customer.subscription.deleted` | Email "Confirmação de cancelamento" |

## Como verificar

1. Acesse https://dashboard.stripe.com/webhooks
2. Clique no seu webhook de produção
3. Em "Eventos para enviar", confirme que **customer.subscription.updated** está na lista
4. Se não estiver, clique em "Atualizar detalhes" e adicione o evento

## Logs de debug

Nos logs do Railway, procure por:
- `[subscription.updated] id=... cancel_at_period_end=True` - webhook recebido
- `Subscription nao encontrada` - assinatura não achada no banco (verificar stripe_subscription_id)
- `Email cancelamento agendado enviado` - email foi enviado
