## QA — Diagnóstico n8n onboarding (webhook 404)

## Resultado do teste
- Signup cria usuário normalmente.
- Email de boas-vindas padrão chega.
- Disparo para n8n falha com:
  - `HTTP Error 404: Not Found`
  - `"The requested webhook ... is not registered."`

## Causa raiz
- URL configurada no Django (`N8N_ONBOARDING_WEBHOOK_URL`) não corresponde a um webhook de produção registrado no n8n **ativo**.
- Mensagem do próprio n8n indica que o workflow precisa estar ativo para URL `/webhook/...`.

## Como validar a correção
1. No n8n, abrir o node Webhook do workflow importado.
2. Copiar a **Production URL** exibida no node (não digitar manualmente).
3. Garantir que o workflow está **Active**.
4. Atualizar `.env`:
   - `N8N_ONBOARDING_WEBHOOK_URL=<Production URL copiada>`
5. Reiniciar Django (`runserver`).
6. Criar novo usuário de teste.

## Expected
- Nova execution aparece no n8n.
- `Check User Status` roda após Delay.
- Branch IF segue por `stage`.

## QA — Correções do workflow n8n onboarding

## O que foi corrigido no arquivo
Arquivo: `docs/n8n/omboarding_check_eduflow.workflow.json`

1. Webhook path alinhado com o `.env`:
   - de `new-user`
   - para `93e4033f-008d-4f18-a5e3-a0a66d784543`

2. Personalização de nome nos e-mails:
   - de `{{$json.name}}` (inexistente no payload)
   - para `{{$json.first_name || $json.username}}`

3. Envio do header `Authorization` na Resend:
   - feito via `options.headers` no node `httpRequest`
   - com `sendHeaders: true` para o n8n realmente aplicar os headers
   - (no seu setup atual, o Bearer pode ainda estar presente no JSON; se você quiser eu ajudo a migrar para env/credentials depois)

## Pré-requisitos
- Workflow reimportado/atualizado no n8n.
- Workflow ativo.
- (opcional) n8n com env `RESEND_API_KEY` configurada (só necessário se você migrar para env em vez de bearer hardcoded)
- Backend com:
  - `N8N_ONBOARDING_WEBHOOK_ENABLED=true`
  - `N8N_ONBOARDING_WEBHOOK_URL=http://localhost:5678/webhook/93e4033f-008d-4f18-a5e3-a0a66d784543`
  - `N8N_ONBOARDING_STATUS_TOKEN=<token>`

## Testes pendentes
### TC-N8N-FIX-1 — Webhook correto recebe evento
1. Criar novo usuário via signup.
2. Verificar execução no n8n.

**Expected**
- O node Webhook é acionado no endpoint com UUID (não `new-user`).

### TC-N8N-FIX-2 — Nome aparece no e-mail
1. Criar usuário com `first_name` preenchido.
2. Forçar um branch (ex.: `missing_student`).
3. Verificar e-mail enviado.

**Expected**
- Texto usa `first_name` (ou `username` fallback).
- Não aparece vazio em lugar do nome.

### TC-N8N-FIX-3 — Authorization header na Resend
1. Executar o workflow (ex.: via signup) para cair no node `Email Missing Student`.
2. Na execução falha/sucesso do node `httpRequest`, abrir detalhes e conferir `Request headers.Authorization` preenchido.
3. Confirmar que não ocorre mais `401 Missing API Key`.

**Expected**
- O node `httpRequest` para `https://api.resend.com/emails` deve aparecer com `Request headers.Authorization` preenchido.
- Resend não responde `401 Missing API Key` (deve avançar para sucesso/erro diferente).

### TC-N8N-FIX-4 — (Opcional) Remover bearer hardcoded do JSON
1. Migrar o bearer para `{{$env.RESEND_API_KEY}}` (ou usar credentials do n8n).
2. Garantir que o header continua chegando na Resend.
3. Executar fluxo.

**Expected**
- Workflow não contém segredo fixo no arquivo JSON.
- A Resend continua recebendo `Authorization`.

## Bug report template
- **Title**: `n8n onboarding: webhook/nome/auth resend incorreto`
- **Execution ID (n8n)**:
- **Stage retornado**:
- **Erro no node**:
- **Expected vs actual**:

## QA — Onboarding automático (n8n + Resend)

## O que foi implementado
- Disparo automático de webhook para n8n ao concluir `signup_view` (início do trial).
- Endpoint interno para o n8n consultar progresso de ativação:
  - `GET /api/internal/onboarding/progress/?user_id=<id>`
  - Protegido por header `X-Internal-Token` (valor: `N8N_ONBOARDING_STATUS_TOKEN`).
- Regras de progresso retornadas:
  - `missing_student` = não criou aluno
  - `missing_lesson` = criou aluno mas não criou aula
  - `missing_homework` = criou aluno e aula, falta atividade
  - `activated` = criou aluno + aula + atividade

## Variáveis de ambiente necessárias
- `N8N_ONBOARDING_WEBHOOK_ENABLED=true`
- `N8N_ONBOARDING_WEBHOOK_URL=http://localhost:5678/webhook-test/93e4033f-008d-4f18-a5e3-a0a66d784543`
- `N8N_ONBOARDING_STATUS_TOKEN=<segredo-forte>`

## Payload enviado para n8n no signup
- `event=trial_started`
- `user_id`, `username`, `email`, `first_name`, `last_name`
- `trial_ends_at`, `started_at`
- `onboarding_check_url`
- `onboarding_check_token`

## Pendências para testar
### TC-N8N-1 — Webhook dispara no signup
1. Garantir env vars acima e backend rodando.
2. Criar novo usuário via signup.
3. Verificar execução no workflow n8n.

**Expected**
- n8n recebe POST com payload completo.

### TC-N8N-2 — Endpoint interno bloqueia acesso sem token
1. Chamar `GET /api/internal/onboarding/progress/?user_id=<id>` sem header `X-Internal-Token`.
2. Chamar com token errado.

**Expected**
- HTTP 401 em ambos.

### TC-N8N-3 — Decisão “missing_student”
1. Criar usuário novo sem cadastrar aluno.
2. n8n espera Delay.
3. n8n consulta endpoint interno com token correto.

**Expected**
- Retorno `stage=missing_student`, `has_student=false`.
- Fluxo IF segue para email: “Você ainda não cadastrou seu primeiro aluno…”.

### TC-N8N-4 — Decisão “missing_lesson”
1. Criar usuário novo.
2. Cadastrar apenas 1 aluno.
3. Aguardar Delay e consulta no endpoint.

**Expected**
- `stage=missing_lesson`, `has_student=true`, `has_lesson=false`.
- IF segue para email: “Agora cria sua primeira aula…”.

### TC-N8N-5 — Decisão “missing_homework”
1. Criar usuário novo.
2. Cadastrar aluno e aula.
3. Não criar homework.
4. Aguardar Delay e consultar endpoint.

**Expected**
- `stage=missing_homework`, `has_student=true`, `has_lesson=true`, `has_homework=false`.

### TC-N8N-6 — Decisão “activated”
1. Criar usuário novo.
2. Cadastrar aluno + aula + homework.
3. Aguardar Delay e consulta.

**Expected**
- `stage=activated`, todos `has_* = true`.
- IF segue para email: “Boa! Você já entendeu como funciona 🎯”.

## Checklist rápido do workflow n8n
1. **Webhook** (já criado)
2. **Delay**
3. **HTTP Request**:
   - Method: GET
   - URL: `{{$json.onboarding_check_url}}?user_id={{$json.user_id}}`
   - Header: `X-Internal-Token: {{$json.onboarding_check_token}}`
4. **IF Node** por `stage`
5. **Resend nodes** (ou HTTP Resend API) para cada branch

## Bug report template
- **Title**: `Onboarding n8n: branch incorreta ou email não enviado`
- **Signup user_id / email**:
- **Webhook execution ID (n8n)**:
- **Stage retornado**:
- **Branch esperada vs atual**:
- **Logs/response HTTP do node de checagem**:

## QA — Área do Aluno pública `/aluno/<token>/`
Status do link (share modal / `aluno_detalhe`): **✅ TC-SHARE-1..3 OK** (não detalhar aqui).

### Pending (o que ainda falta testar)
### TC-AREA-1 — Sem mock: KPIs e topo dependem do token
1. Abrir `/aluno/<token>/` do aluno A.
2. Verificar se KPIs e textos (aulas e homework) refletem os dados reais dele (sem valores fixos).
3. Abrir `/aluno/<token>/` do aluno B.

**Expected**
- Os dados mudam de A para B (sem “pacote hardcoded”).

### TC-AREA-2 — Materiais reais (sem hardcode)
1. Abrir `/aluno/<token>/` e ir na aba **Materiais**.
2. Verificar que meses/datas, títulos e links “Abrir material” correspondem a `LessonPlanAttachment` do aluno.

**Expected**
- Renderiza apenas anexos do aluno do token.

### TC-AREA-3 — Homework renderiza pendentes e concluídos
1. Na aba **Homework**, verificar grupo **Em andamento** (`pending`) e **Concluído** (`done`).
2. Validar `Prazo`, descrição e conteúdo visível contra `StudentHomework` real do aluno.

**Expected**
- Contagens e cards batem com o backend.

### TC-AREA-4 — Comentário do aluno persiste (happy path)
1. Selecionar um homework pendente (`pending`) em **Em andamento**.
2. Preencher o `<textarea>` e clicar **Enviar comentário**.
3. Recarregar a página e voltar na mesma aba.

**Expected**
- O comentário volta persistido no card (fonte `student_response`).

### TC-AREA-5 — Comentário vazio (edge)
1. Abrir `/aluno/<token>/` e clicar **Enviar comentário** sem preencher texto.

**Expected**
- Mostra erro/feedback e não altera o `student_response`.

### TC-AREA-6 — Token inválido/revogado (error)
1. Usar um token inválido (ou revogar e tentar reutilizar).

**Expected**
- `/aluno/<token>/` retorna 404.

### TC-AREA-7 — homework_id inválido para aquele token (error)
1. Enviar via Network/DevTools:
   - `POST /api/public/area-aluno/<token>/homeworks/<homework_id>/comment/`
   - usando um `homework_id` de outro aluno.

**Expected**
- Resposta 404 “Homework não encontrado” e nenhum dado muda.

## Bug reporting template
- **Title**: `Área do Aluno: dados incorretos (mock) ou comentário não persiste`
- **URL**: `/aluno/<token>/`
- **Role**: aluno / professor (owner)
- **Console errors**: copy/paste
- **Network** (se for comentário):
  - `POST /api/public/area-aluno/<token>/homeworks/<homework_id>/comment/`
- **Steps** + **Expected vs actual**

## Área do Aluno — Link de Acesso (share modal)
Status: OK (testes executados)

### O que foi garantido
1. Modal “Área do Aluno” carrega uma URL real com token (`tok_...`).
2. “Gerar novo link” revoga o token anterior e cria outro.
3. WhatsApp e E-mail compartilham exatamente o link atual do modal.

### Testes (TC-SHARE)
TC-SHARE-1 ✅ — Modal abre, URL real carregada (tok_...), página pública retorna 200 com nome do aluno e `teacher_name` corretos.
TC-SHARE-2 ✅ — “Gerar novo link” revoga token antigo (→ 404) e cria novo (→ 200). `#shareUrl` atualiza no modal.
TC-SHARE-3 ✅ — WhatsApp e E-mail usam exatamente o link atual do modal.

### Referência
- `GET /api/students/<id>/share-link/`
- `POST /api/students/<id>/share-link/regenerate/`
- rota pública: `/aluno/<token>/`

## Área do Aluno — Link de Acesso (share modal)
Status: OK (testes executados)

### O que foi garantido
1. Modal **“Área do Aluno”** carrega **uma URL real** com token (`tok_...`).
2. **“Gerar novo link”** revoga o token anterior e cria outro.
3. WhatsApp e E-mail compartilham **exatamente** o link atual do modal.

### Testes (TC-SHARE)
TC-SHARE-1 ✅ — Modal abre, URL real carregada (tok_...), página pública retorna 200 com nome do aluno e `teacher_name` corretos.
TC-SHARE-2 ✅ — “Gerar novo link” revoga token antigo (→ 404) e cria novo (→ 200). `#shareUrl` atualiza no modal.
TC-SHARE-3 ✅ — WhatsApp e E-mail usam exatamente o link atual do modal.

### Referência (quando necessário)
- `GET /api/students/<id>/share-link/`
- `POST /api/students/<id>/share-link/regenerate/`
- rota pública: `/aluno/<token>/`

## Activity completed (latest)
**Feature:** Área do Aluno pública (`/aluno/<token>/`) integrada com dados reais (removendo mock/hardcoded) + envio de **comentário/resposta do aluno** no homework via token.

## Root cause (context)
- `frontend/templates/area_aluno.html` foi um mockup de design e exibia 100% hardcoded (ex.: 24 aulas, 78% HW, “Março 2026”, tópicos fixos), fazendo todos os alunos verem o mesmo conteúdo fictício.
- O envio de comentário no homework na área pública era apenas UI (não persistia no backend).

## What was changed
- **Backend (`core`)**
  - `StudentAreaView` agora injeta no template dados reais por token:
    - Próxima aula e última aula realizada
    - KPIs (aulas realizadas, % e contagem de homework)
    - Listas de homework (pendentes/concluídos) + campos `student_response`/`teacher_feedback`
    - Materiais reais via `LessonPlanAttachment` agrupados por mês/data
    - Calendário do mês atual (dias com aulas realizadas/agendadas e lista de aulas)
  - Endpoint público por token:
    - `POST /api/public/area-aluno/<token>/homeworks/<homework_id>/comment/`
    - Atualiza `StudentHomework.student_response` do homework pertencente ao aluno daquele token

- **Frontend (`frontend/templates/area_aluno.html`)**
  - Renderização em JS substitui o HTML mock dos tabs `Materiais`, `Homework` e `Calendário` com dados reais vindos do backend.
  - Cards de homework pendente passam a exibir `<textarea>` e botões reais.
  - `submitComment()` agora chama o endpoint público por token e exibe feedback (toast).

## Files touched
- `core/views.py`
- `core/urls.py`
- `frontend/templates/area_aluno.html`
- `docs/QA_AGENT_TASK.md`

## Prerequisites
1. App rodando: `python manage.py runserver`
2. Existir ao menos 1 `Student` com:
   - Lessons criadas (para validar KPIs e calendário)
   - Homeworks criadas (pendente e/ou concluída) com `student_response`/`teacher_feedback`
   - Lesson plans + anexos (`LessonPlanAttachment`) para validação de Materiais
3. Ter um token válido:
   - Abrir `aluno_detalhe` e clicar em **Área do Aluno** para gerar/copiar o link `/aluno/<token>/`

## Test cases (step-by-step)
### TC-AREA-1 — Sem mock: KPIs e topo dependem do token
1. Abrir `/aluno/<token>/` de um aluno A.
2. Verificar:
   - nome do aluno no topo
   - `% HW` e contagens batem com os registros reais (`StudentHomework`)
   - “Próxima aula” e “Última aula” batem com `Lesson.realized/status/date/time`
3. Abrir `/aluno/<token>/` de um aluno B (diferente de A).

**Expected**
- Nunca aparece mais o pacote hardcoded (24 aulas, “Present Perfect”, “Março 2026”, etc.).
- KPIs e calendário mudam conforme o aluno do token.

### TC-AREA-2 — Materiais carregam reais (sem hardcode)
1. Abrir `/aluno/<token>/`.
2. Ir na aba **Materiais**.
3. Conferir:
   - meses/datas mostrados condizem com `LessonPlanAttachment.lesson_plan.date`
   - o título/descrição e link “Abrir material” batem com os anexos reais.

**Expected**
- Materiais renderizados são do aluno do token (não fixos).

### TC-AREA-3 — Homework pendente e concluída renderizam corretamente
1. Abrir `/aluno/<token>/` e ir em **Homework**.
2. Verificar:
   - grupo “Em andamento” mostra homeworks `status=pending`
   - grupo “Concluído” mostra homeworks `status=done`
   - `Prazo` e campos de descrição batem com `StudentHomework`.

**Expected**
- Lista e contagens refletem exatamente a base.

### TC-AREA-4 — Envio de comentário persiste (happy path)
1. Na aba **Homework**, dentro do grupo **Em andamento**, localizar um homework pendente.
2. Preencher o `<textarea>` com um texto (ex.: “Tive dúvida no exercício X…”).
3. Clicar em **Enviar comentário**.
4. Observar toast/feedback de sucesso.
5. Recarregar a página (`F5`) e voltar na mesma aba.

**Expected**
- Comentário salva no backend e reaparece no card após recarregar (fonte `student_response`).
- UI não fica travada e não quebra em console.

### TC-AREA-5 — Comentário vazio (edge)
1. Abrir `/aluno/<token>/` e tentar enviar com textarea vazio.

**Expected**
- Deve mostrar erro/feedback e não chamar a API de update (ou API falha sem persistir).

### TC-AREA-6 — Token inválido (error)
1. Alterar o link `/aluno/<token>/` manualmente para um token inválido/revogado.

**Expected**
- Página `/aluno/<token>/` retorna 404.

### TC-AREA-7 — Homework_id inválido para aquele token (error)
1. Via DevTools/Network, chamar:
   - `POST /api/public/area-aluno/<token_do_aluno_A>/homeworks/<id_de_hw_de_aluno_B>/comment/`
2. Observar resposta.

**Expected**
- Retorna 404 “Homework não encontrado”.
- Nenhuma alteração ocorre no homework de B.

## Bug reporting template
- **Title**: `Área do Aluno: dados continuam hardcoded ou comentário não persiste`
- **URL**: `/aluno/<token>/`
- **Role**: aluno / professor (owner)
- **Console errors**: copy/paste
- **Network** (quando aplicável):
  - `POST /api/public/area-aluno/<token>/homeworks/<homework_id>/comment/`
- **Steps** + **Expected vs actual**

## Activity completed (latest)
**Feature:** Área do Aluno — Link de Acesso (modal em `aluno_detalhe`)

**Fixes:** o modal deixou de usar URL fixa (mock) e passou a carregar um link real por token; **“Gerar novo link”** agora regenera via backend.

## Root cause (context)
- `frontend/templates/aluno_detalhe.html` exibía uma URL de exemplo hardcoded no `#shareUrl`.
- `regenerateLink()` apenas mostrava toast e não regenerava token/URL.

## What was changed
- Backend (`core`):
  - Modelo `StudentShareToken`.
  - `GET /api/students/<id>/share-link/` retorna a URL atual (gera token se necessário).
  - `POST /api/students/<id>/share-link/regenerate/` revoga token ativo e gera um novo.
  - Rota pública `/aluno/<token>/` renderiza `area_aluno.html` baseado no token.
- Frontend:
  - Ao abrir o modal, chama a API e atualiza `#shareUrl`.
  - “Gerar novo link” chama a API e atualiza `#shareUrl`.
  - WhatsApp/E-mail usam o link atual do modal.
- `area_aluno.html`: topo agora usa `student`/`teacher_name` em vez de texto hardcoded.

## Files touched
- `core/models.py`
- `core/views.py`
- `core/urls.py`
- `frontend/templates/aluno_detalhe.html`
- `frontend/templates/area_aluno.html`
- `docs/QA_AGENT_TASK.md` (esta atualização)

## Prerequisites
- App rodando (`python manage.py runserver`).
- Estar logado como **professor** dono (ou parceiro, se aplicável) de pelo menos 1 aluno.
- Ter um aluno acessível em `/alunos/`.

## Test cases (step-by-step)
### TC-SHARE-1 — Abrir modal e copiar link (happy path)
1. Abrir `/alunos/` e entrar na ficha do aluno (ou `/alunos/<student_id>/`).
2. Clicar em **“Área do Aluno”**.
3. Confirmar que `#shareUrl` sai de “Carregando...”.
4. Clicar em **Copiar**.

**Expected**
- `#shareUrl` contém uma URL `.../aluno/tok_<...>/`.
- Toast “Link copiado!” aparece.
- Abrindo em nova aba a URL `/aluno/<token>/`, a página carrega e exibe nome do aluno e topo com `teacher_name`.

### TC-SHARE-2 — Regenerar link invalida o anterior (token muda)
1. Com o modal aberto, copiar/registrar a URL antiga do `#shareUrl`.
2. Clicar em **“Gerar novo link”**.
3. Confirmar toast “Novo link gerado!”.
4. Confirmar que `#shareUrl` mudou (URL nova != URL antiga).
5. Abrir em nova aba a URL antiga.

**Expected**
- Token muda (`tok_...` diferente).
- URL antiga retorna **404**.
- URL nova retorna **200**.

### TC-SHARE-3 — Compartilhar WhatsApp/E-mail usa o link atual
1. Abrir modal e confirmar link carregado.
2. Clicar **WhatsApp** e validar que o texto contém o link atual.
3. Clicar **E-mail** e validar que o corpo contém o link atual.

**Expected**
- WhatsApp/E-mail usam exatamente o link que está em `#shareUrl`.

## Error scenarios
### ERR-SHARE-1 — Sem autenticação
1. Deslogar.
2. Tentar acessar `/alunos/<id>/`.

**Expected**
- Redireciona para login.

### ERR-SHARE-2 — Permissão/Aluno inválido
1. Logar como professor A.
2. Tentar chamar via DevTools uma API com `student_id` que não pertence ao professor A.

**Expected**
- 404/403 com mensagem de “sem permissão”.

## Bug reporting template
- **Title**: "Aluno detalhe: modal Área do Aluno não carrega ou não regenera token"
- **URL**: `/alunos/<student_id>/` e/ou `/aluno/<token>/`
- **Role**: owner / partner
- **Console errors**: copy/paste
- **Network**:
  - `GET /api/students/<id>/share-link/`
  - `POST /api/students/<id>/share-link/regenerate/`
- **Steps** + **Expected vs actual**

## Activity completed (latest)
**Feature:** Calendário original (Nova Aula): após criar um agendamento, oferecer modal para **replicar automaticamente** a mesma aula nas próximas datas do mesmo dia da semana restantes no mês (todas como **Pendente**).

**Fixes:** ajustei a UX do modal (botões não ficam cortados) e garanti atualização automática do calendário após replicar (sem precisar trocar de tela/F5).

## Root cause (context)
- Necessidade de reduzir esforço manual do professor: ao cadastrar uma aula recorrente (ex.: toda quarta), o sistema deve sugerir automaticamente as próximas ocorrências do mesmo mês.

## What was changed
- No `frontend/templates/calendar_new.html`:
  - Adicionei um modal novo `#modalReplicateLesson` com UX limpa e botões claros.
  - Após `POST /api/calendar/events/create/` (modo **criar nova** aula), o frontend calcula as próximas datas do **mesmo dia da semana** dentro do mesmo mês e abre o modal se houver alguma sugestão.
  - Ao clicar **Replicar**, o frontend cria as demais aulas via `POST /api/calendar/events/create/` para cada data sugerida, forçando `status: "pending"`.
  - Ao clicar **Agora não**, o fluxo segue sem criar eventos extras.

## Files touched
- `frontend/templates/calendar_new.html`
- `docs/QA_AGENT_TASK.md` (esta atualização)

## Prerequisites
- App rodando e usuário logado.
- Existir pelo menos 1 aluno ativo (ex.: “Joao”).

## Test cases (step-by-step)

### TC-REPL-1 — Modal aparece e replica a aula (caso do exemplo)
1. Abrir a tela original de calendário: `/calendar/`.
2. Criar uma **nova aula** (abrir modal “Nova Aula”).
3. Selecionar o aluno `Joao`.
4. Definir `Data` como uma data que tenha o mesmo dia da semana restante no mês (ex.: **18/03/2026** se o mês for março/2026, com próxima quarta **25/03/2026**).
5. Definir `Horário` (ex.: 18:00) e salvar.
6. Após salvar, observar se aparece o modal “Replicar Aula no Mês”.
7. No modal, clicar em **Replicar**.

**Expected**
- O modal aparece mostrando as **datas sugeridas** (pills/chips).
- O sistema cria automaticamente as aulas replicadas nas datas sugeridas.
- Um toast confirma a replicação (ou feedback visual equivalente).
- As aulas replicadas aparecem no calendário como **Pendente**.

### TC-REPL-2 — Modal não aparece quando não há datas restantes
1. Abrir `/calendar/`.
2. Criar uma nova aula escolhendo uma data em que **não existe** outra ocorrência do mesmo dia da semana no restante do mês (ex.: “última quarta” do mês).

**Expected**
- A tela salva a aula normalmente.
- O modal de replicação **não** aparece.

### TC-REPL-3 — Replicação força status “pending” mesmo se a aula criada não for pendente
1. Criar nova aula com `Data` tendo pelo menos 1 ocorrência restante no mês.
2. No campo `Status`, selecionar algo diferente de “Pendente” (ex.: “Confirmado”).
3. Salvar.
4. Quando o modal aparecer, clicar **Replicar**.

**Expected**
- As aulas replicadas são criadas como **Pendente** (independente do status escolhido na aula original).

### TC-REPL-4 — Não deve replicar ao editar uma aula existente
1. No calendário, abrir/editar uma aula existente (modo “Salvar Alterações”, não “Criar Aula”).
2. Salvar alterações.

**Expected**
- O modal de replicação **não** aparece.

### TC-REPL-5 — Tratamento de erro de vinculação (smoke)
1. Cenário: aluno não vinculado ao professor parceiro (quando aplicável).
2. Criar aula falhando com erro de vinculação (garantir que o frontend lida com isso).
3. Se a criação base falhar, não deve abrir modal.
4. Se a criação base for permitida e o modal abrir, clicar **Replicar**.

**Expected**
- Se API retornar erro de `student_assignment`, o frontend deve exibir o modal de erro/feedback existente (sem “silenciar” o erro).

### TC-REPL-6 — Modal UX (botões totalmente visíveis)
1. Abrir o modal “Replicar Aula no Mês”.
2. Observar a área inferior do modal (em telas menores).

**Expected**
- Botões “Agora não” e “Replicar” ficam totalmente visíveis.
- O conteúdo do modal pode rolar sem empurrar os botões para fora da área visível.

### TC-REPL-7 — Atualização automática após clicar “Replicar”
1. Criar uma aula que dispare o modal.
2. No modal, clicar **Replicar**.
3. Sem sair da tela, observar o calendário imediatamente.

**Expected**
- O calendário atualiza automaticamente.
- As novas aulas replicadas aparecem sem F5 e sem precisar ir para outra tela e voltar.

### TC-REPL-8 — Visual premium do modal
1. Abrir o modal “Replicar Aula no Mês”.

**Expected**
- Modal com header e container mais “premium” (não chapado).
- Seção “Datas sugeridas” em card com borda suave.
- Chips com borda/sombra leve, com aparência distinta do modal anterior.

## Bug reporting template
- **Title**: "Calendar: replicação não aparece ou cria eventos incorretos"
- **URL**: `/calendar/` (mês/semana em que testou)
- **Role**: owner / partner / admin
- **Console errors**: copy/paste
- **Network**: `POST /api/calendar/events/create/` (quantidade de chamadas = 1 + nº de datas sugeridas)
- **Steps** + **Expected vs actual**

