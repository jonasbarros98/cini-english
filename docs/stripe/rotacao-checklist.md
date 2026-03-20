# ✅ Checklist: Rotação da Chave Stripe

Você já trocou a `STRIPE_SECRET_KEY` no Railway. Confira o resto:

---

## 1. Railway – variável atualizada ✅

- [x] `STRIPE_SECRET_KEY` = nova chave (já feito)

**Importante:** O Railway só usa a variável nova depois que o app reinicia.

- [ ] **Redeploy:** No Railway → seu serviço → **Deploy** ou **Redeploy**  
  - Se o deploy for automático pelo Git, um novo push já provoca redeploy.  
  - Se não, clique em **Redeploy** depois de alterar a variável.

---

## 2. O que **não** precisa mudar

- **`STRIPE_PRICE_ID_MONTHLY`** / **`SEMESTRAL`** / **`ANNUAL`**  
  São IDs de preços, não da chave. Continuam os mesmos.

- **`STRIPE_WEBHOOK_SECRET`**  
  É o secret do webhook, independente da API key. Só troque se o Stripe orientar ou se você gerar um novo endpoint de webhook.

---

## 3. Desenvolvimento local (`.env`)

Se você roda o projeto localmente:

- [ ] Atualize o `.env` com a **chave de teste** nova (se você tiver rotacionado também a chave de teste).  
- Use sempre `sk_test_...` no `.env` e `sk_live_...` apenas no Railway.

---

## 4. Testar em produção

Depois do redeploy:

1. Acesse a landing em produção.
2. Faça um checkout (plano → cadastro → pagamento).
3. Confirme que o redirecionamento e o processamento funcionam.
4. Em **Stripe Dashboard → Webhooks**, verifique se os eventos continuam chegando (ex.: `checkout.session.completed`).

Se o checkout e os webhooks funcionarem, a rotação está ok.

---

## Resumo

| Item                         | Ação                          |
|-----------------------------|-------------------------------|
| `STRIPE_SECRET_KEY` Railway | ✅ Já atualizado              |
| Redeploy no Railway         | Fazer se ainda não fez        |
| Price IDs                   | Manter como estão             |
| Webhook secret              | Manter, a menos que Stripe diga o contrário |
| `.env` local                | Atualizar se usar chave de teste local      |

Depois do **Redeploy** no Railway e dos testes acima, não costuma ser necessário fazer mais nada.
