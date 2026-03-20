# Garantia: Falhas de Email Não Interrompem o Sistema

Este documento descreve como o sistema garante que **usuários ativos nunca sejam impactados** quando o envio de emails falha no Railway (SMTP timeout, credenciais incorretas, etc.).

---

## Resumo

**Todos os fluxos que enviam email continuam funcionando mesmo quando o email não é entregue.**

| Fluxo | Comportamento se email falhar |
|-------|------------------------------|
| Cadastro (signup) | Usuário é criado e pode fazer login. Email de boas-vindas não é enviado, mas o cadastro completa. |
| Formulário de contato (landing) | Mensagem é “recebida” e retorna sucesso. Email pode não chegar, mas o usuário não vê erro. |
| Ticket de suporte | Ticket é salvo no banco. Email pode não ir, mas o ticket fica registrado. |
| Cron: onboarding 24h | Comando termina com exit 0. Próximo usuário é processado. |
| Cron: recuperação pendente | Idem. |

---

## Medidas Técnicas

### 1. `fail_silently=True` em todos os `send_mail`

O Django não levanta exceção quando o envio falha — apenas retorna 0.

### 2. Try/except em todos os fluxos

- **Signup:** `try/except` em volta do envio do email de boas-vindas.
- **Landing contact:** `try/except` em qualquer operação relacionada a email.
- **Support ticket:** `try/except` captura qualquer erro e nunca re-levanta.
- **Comandos de cron:** cada envio por usuário em `try/except`; o comando inteiro em `try/except` para erros inesperados.

### 3. `EMAIL_TIMEOUT = 10` segundos

Evita bloqueio longo em caso de SMTP lento ou indisponível.

### 4. Comandos Cron sempre saem com exit 0

Erros inesperados são logados e o comando termina normalmente, sem falhar o job no Railway.

### 5. Separação de responsabilidades

Os comandos de cron rodam em **serviços separados** do app web. Se o cron cair ou falhar, o app principal e os usuários ativos não são afetados.

---

## O que pode acontecer

- Email de boas-vindas não chega → usuário ainda usa o sistema normalmente.
- Formulário de contato sem entrega → modal mostra sucesso; você pode não receber a mensagem.
- Ticket sem email → ticket aparece no admin, mas o destinatário não recebe notificação.
- Cron de emails não roda → nenhum email automático é enviado; o uso do sistema continua normal.

---

## O que NÃO acontece

- Nenhum fluxo do usuário retorna erro 500 por falha de email.
- Nenhum cadastro ou operação é interrompida por timeout ou erro de SMTP.
- Falhas de cron não impedem o uso do app pelos usuários ativos.
