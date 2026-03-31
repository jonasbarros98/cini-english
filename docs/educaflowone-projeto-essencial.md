# EducaflowOne — o essencial do projeto

Este arquivo é um **guia de entrada** para qualquer pessoa ou IA que vá trabalhar neste repositório. Resume **o que é o produto**, **como o código se organiza** e **onde buscar detalhes**. Não substitui os manuais temáticos em `docs/` (Stripe, deploy, QA, etc.).

---

## O que é o EducaflowOne

**EducaflowOne** é um **SaaS em português** para **professores particulares** gerirem o dia a dia: **alunos**, **agenda/aulas**, **planejamento**, **financeiro** (a receber / recebido / vencido), **cobrança** (mensagens prontas, uso comum com WhatsApp/Pix) e **materiais** (anexos por aluno, biblioteca de arquivos do professor).

O **cliente pagador da assinatura** é o professor (conta `User` dona dos dados). Existe **trial de 7 dias sem cartão**; depois, assinatura via **Stripe** (planos, webhooks, portal).

O repositório local às vezes aparece como **“Cini English”** (nome histórico da pasta); o produto comercial é **EducaflowOne**. Site de referência: `https://www.educaflowone.com.br`.

---

## Público e linguagem

- **Usuário principal:** professor autônomo (muito idiomas, mas não só).
- **UI e cópia:** predominantemente **português (Brasil)**; tom direto, poucos cliques, foco em rotina real (não “ERP genérico”).
- **Aluno/responsável:** pode ter **área pública** por link com token (`/aluno/<token>/`), sem login na plataforma.

---

## Stack técnica (visão rápida)

| Camada | Tecnologia |
|--------|------------|
| Backend | **Python**, **Django 6**, **Django REST Framework** |
| Frontend app | **Templates Django** + HTML/CSS/JS em `frontend/templates/` e estilos em `core/static/` (e `staticfiles/` gerado) |
| Banco | Configurado via env (ex.: PostgreSQL em produção) |
| Deploy | **Railway** (Docker), proxy HTTPS, variáveis de ambiente |
| Mídia / anexos | **Cloudflare R2** (S3-compatible) quando `USE_R2_STORAGE`; senão filesystem |
| Estáticos | **WhiteNoise** + `collectstatic` no build (cuidado: backend de `staticfiles` deve ser o mesmo em build e produção) |
| Pagamentos | **Stripe** (checkout, customer portal, webhooks) |
| E-mail | SMTP / provedores (ex. Resend); vários fluxos transacionais e campanhas admin |

Regra prática para agentes: **mudanças de comportamento** costumam estar em `core/views.py`, `core/urls.py`, `core/models.py`; **HTML** em `frontend/templates/`; **CSS global** em `core/static/styles.css`.

---

## Pastas importantes no repositório

- `config/` — projeto Django (`settings.py`, `urls.py` raiz inclui `core.urls`).
- `core/` — app principal: **models**, **views**, APIs, integrações (Stripe, e-mails), estáticos do app.
- `frontend/templates/` — páginas (dashboard, calendário, alunos, admin panel, landings, etc.).
- `docs/` — documentação por tema (Stripe, deploy, produto). **Índice:** [docs/README.md](README.md).
- `Dockerfile` — imagem de deploy; inclui `collectstatic`.
- `.env` — **não commitar segredos**; uso local/produção via variáveis de ambiente.

---

## Funcionalidades que você precisa reconhecer (lista curta)

1. **Dashboard** — resumo do mês, links rápidos (`/dashboard/`).
2. **Calendário** — aulas por dia, status, notas (`calendar_new` / APIs em `core/urls.py`).
3. **Alunos** — cadastro, planos (mensal, pacote, por aula, etc.), ficha detalhada, materiais, share link.
4. **Planejamento** — planos de aula, anexos.
5. **Financeiro** — lançamentos, filtros, gêmeo com regras de cobrança.
6. **Cobrança** — textos e logs (`BillingLog`).
7. **Área do aluno** — página pública por token; deveres/comentários conforme implementado.
8. **Agendamento público** — `/agendar/<slug>/` e APIs `public_*`.
9. **Arquivos (biblioteca do professor)** — rota/API relacionada a `ArquivosView`, `teacher_materials`, etc.
10. **Autenticação** — login, signup, Google OAuth (redirect URI HTTPS atrás de proxy).
11. **Painel admin interno** — `painel-admin/`: métricas, e-mails de retenção, **campanhas de feature**, testes de e-mail de assinatura (rotas `api/admin/...`).
12. **Landings** — várias versões (`landing-v5`, `landing-v7`, etc.); marketing e testes A/B evoluem aqui.
13. **Superuser Django** — `admin/` padrão, além do painel customizado.

Para **visão de produto mais rica** (pilares, intenção de UX), leia: [product-design/educaflow-overview.md](product-design/educaflow-overview.md).

---

## Conceitos de dados (sem esgotar o modelo)

- **`User`** — professor (dono). Pode ter **professores parceiros** (alunos atribuídos a outro usuário).
- **`Student`** — aluno; ligado a `user` (professor dono); plano, contatos, contrato, Pix, nível CEFR opcional.
- **`Lesson`** — aula no calendário, status, ligação com aluno.
- **`FinancialEntry`**, **`Invoice`**, **`BillingLog`** — fluxo financeiro e cobrança.
- **`LessonPlan`**, anexos de planejamento, materiais de aluno/professor — arquivos em storage configurável (R2 ou disco).

Antes de alterar schema: **migrações Django** (`makemigrations` / `migrate`).

---

## O que pedir ao implementar algo novo

1. **Não quebrar produção:** usuários reais; testar static/media/Stripe/emails com cuidado.
2. **Seguir padrões existentes** nos templates e em `core/views.py` (DRF, permissões, CSRF em POST).
3. **Anexos:** usar `FileField` + storage atual; exclusão deve tolerar arquivo ausente no bucket (há padrão de delete seguro em views).
4. **E-mails:** templates HTML costumam ser inline/table-based; há logs de campanha (`FeatureEmailCampaign` / `FeatureEmailLog`) no painel admin.

---

## Referências rápidas

| Preciso de… | Onde |
|-------------|------|
| Índice geral da documentação | [docs/README.md](README.md) |
| Visão de produto detalhada | [product-design/educaflow-overview.md](product-design/educaflow-overview.md) |
| Rotas e APIs | `core/urls.py` |
| Modelos | `core/models.py` |
| Config / env / storage / static | `config/settings.py` |
| Incidentes / ops (ex.: R2, static) | `docs/educaflow-codebase-expert/` (se existir) e notas em `docs/deploy-ops/` |

---

*Última intenção deste doc: qualquer agente ou colaborador entender em minutos **para quem** o sistema existe, **com que stack** roda e **onde mexer** para executar tarefas futuras sem reinventar o contexto.*
