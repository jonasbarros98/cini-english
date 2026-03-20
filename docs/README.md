# Documentação do projeto (Cini English / EDUCAflowOne)

Índice central. Os ficheiros `.md` que estavam na raiz do repositório foram organizados aqui por tema.

---

## Aluno detalhe (ficha do aluno)

| Ficheiro | Conteúdo |
|----------|----------|
| [aluno-detalhe/checklist.md](aluno-detalhe/checklist.md) | Checklist histórico: UI, o que falta vs produção |
| [aluno-detalhe/qa-testing.md](aluno-detalhe/qa-testing.md) | Guia de testes QA: happy path, edge cases, bugs |
| [aluno-detalhe/backend-plano.md](aluno-detalhe/backend-plano.md) | Plano backend / integração |

---

## Stripe (pagamentos)

| Ficheiro | Conteúdo |
|----------|----------|
| [stripe/setup.md](stripe/setup.md) | Configuração Stripe |
| [stripe/webhook-events.md](stripe/webhook-events.md) | Eventos de webhook |
| [stripe/webhook-fix.md](stripe/webhook-fix.md) | Correções webhook |
| [stripe/production-migration.md](stripe/production-migration.md) | Migração produção |
| [stripe/rotacao-checklist.md](stripe/rotacao-checklist.md) | Checklist rotação chaves |

---

## Deploy e operações

| Ficheiro | Conteúdo |
|----------|----------|
| [deploy-ops/pre-deploy-checklist.md](deploy-ops/pre-deploy-checklist.md) | Antes de publicar |
| [deploy-ops/railway-deploy-guide.md](deploy-ops/railway-deploy-guide.md) | Deploy Railway |
| [deploy-ops/railway-cron-email-24h.md](deploy-ops/railway-cron-email-24h.md) | Cron e-mail 24h |

---

## E-mail

| Ficheiro | Conteúdo |
|----------|----------|
| [email/contact-setup.md](email/contact-setup.md) | Contacto / e-mail |
| [email/failure-guarantee.md](email/failure-guarantee.md) | Garantias em falha de e-mail |

---

## Produto e design

| Ficheiro | Conteúdo |
|----------|----------|
| [product-design/area-aluno-design.md](product-design/area-aluno-design.md) | Área do aluno — análise |
| [product-design/landing-v4-analise.md](product-design/landing-v4-analise.md) | Landing v4 |
| [product-design/educaflow-overview.md](product-design/educaflow-overview.md) | Visão geral EDUCAflowOne |

---

## Git / repositório

| Ficheiro | Conteúdo |
|----------|----------|
| [git/git-push-solution.md](git/git-push-solution.md) | Push Git |
| [git/solucao-push-github.md](git/solucao-push-github.md) | Solução push GitHub |

---

## Diversos

| Ficheiro | Conteúdo |
|----------|----------|
| [misc/trial-flow.md](misc/trial-flow.md) | Fluxo trial |
| [misc/resposta-ticket-alunos.md](misc/resposta-ticket-alunos.md) | Resposta ticket alunos |
| [misc/homework-notifications-bell.md](misc/homework-notifications-bell.md) | Sininho de notificações (mensagens de tarefas) |

---

## Fora desta pasta (propositadamente)

| Local | Motivo |
|-------|--------|
| `README.md` (raiz) | Entrada principal do repositório |
| `.github/copilot-instructions.md` | Instruções do Copilot no sítio padrão |
| `_backup/*.md` | Backup legado |
| `staticfiles/**` | Ficheiros de terceiros (Django admin, licenças) |

---

*Ao adicionar documentação nova, coloque-a na subpasta mais adequada e atualize este índice.*
