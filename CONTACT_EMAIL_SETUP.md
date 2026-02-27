# Configuração de Emails do EDUCAflowOne

## Formulário de contato da landing

O formulário "Entre em contato" na landing page envia os dados para **educaflowone@gmail.com**.

## Como funciona

- Ao clicar em "Entre em contato conosco", abre um modal na mesma página
- Campos: Nome, WhatsApp ou Email, Dúvida
- O envio é feito via `POST /api/landing/contact/`
- O backend envia um email para `CONTACT_EMAIL` (educaflowone@gmail.com)

---

## ⭐ Recomendado no Railway: Resend (API)

O **Railway bloqueia portas SMTP** (465, 587) em planos Free, Trial e Hobby. Por isso Gmail/SMTP não funciona em produção no Railway. Use **Resend**, que envia via API HTTPS (porta 443).

### 1. Criar conta no Resend

1. Acesse [resend.com](https://resend.com) e crie uma conta
2. No painel: **Domains** → **Add Domain** → adicione `educaflowone.com.br`
3. Adicione os registros DNS (DKIM, SPF, DMARC) que o Resend indicar no seu provedor de DNS
4. Clique em **Verify** quando os registros estiverem propagados (pode levar até 48h, geralmente minutos)
5. Em **API Keys**, crie uma chave e copie

### 2. Variáveis de ambiente no Railway

```env
# Resend (prioridade sobre SMTP - use no Railway)
RESEND_API_KEY=re_xxxxxxxxxxxx
DEFAULT_FROM_EMAIL=contato@educaflowone.com.br
CONTACT_EMAIL=educaflowone@gmail.com
```

O `DEFAULT_FROM_EMAIL` deve ser um endereço **@educaflowone.com.br** (domínio verificado no Resend).

### 3. Deploy e teste

Faça deploy e envie o formulário de contato. O email deve chegar em `CONTACT_EMAIL`.

---

## Alternativa: Gmail SMTP (só funciona local ou em hosts que permitem SMTP)

Para que os emails cheguem de fato na caixa de entrada, configure as variáveis de ambiente:

### 1. Usando Gmail (educaflowone@gmail.com)

Crie uma **Senha de app** no Gmail:
1. Acesse https://myaccount.google.com/security
2. Ative verificação em 2 etapas (se ainda não estiver)
3. Em "Senhas de app", crie uma nova senha para "Outro (nome personalizado)" → "EDUCAflowOne"
4. Copie a senha de 16 caracteres

### 2. Variáveis de ambiente (.env ou Railway/Vercel)

```env
# Email SMTP (Gmail)
EMAIL_HOST_USER=educaflowone@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx

# Opcional: customizar
DEFAULT_FROM_EMAIL=educaflowone@gmail.com
CONTACT_EMAIL=educaflowone@gmail.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=465
```

### 3. Django settings (já configurado)

O `config/settings.py` já lê essas variáveis:
- `EMAIL_HOST_USER` e `EMAIL_HOST_PASSWORD` → ativa o SMTP real
- Sem elas, o Django usa `console backend` (imprime o email no terminal)

### 4. Testar

1. Inicie o servidor: `python manage.py runserver`
2. Acesse a landing (sem login)
3. Clique em "Entre em contato conosco"
4. Preencha e envie

Se SMTP estiver configurado, o email chegará em educaflowone@gmail.com.  
Se não, verá o email impresso no terminal.

## Alternativa: outros provedores SMTP

Para SendGrid, Mailgun, Amazon SES etc., ajuste:

```env
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=sua_api_key
```

---

## Email de onboarding 24h (pós-cadastro + assinatura ativa)

Após cadastro **e** assinatura de um plano, 24 horas depois enviamos um email de engajamento: "Você já cadastrou seu primeiro aluno?".

### Como ativar

1. **Rodar a migração:**
   ```bash
   python manage.py migrate
   ```

2. **Agendar o comando** para rodar a cada hora (cron no servidor ou Railway Cron):

   **Linux / cron:**
   ```bash
   0 * * * * cd /caminho/do/projeto && python manage.py send_onboarding_24h_email
   ```

   **Railway:** adicione um Cron Job no dashboard apontando para:
   ```bash
   python manage.py send_onboarding_24h_email
   ```

3. **URL do site** (para o link de login no email): configure no `.env`:
   ```env
   SITE_URL=https://educaflowone.com.br
   ```
