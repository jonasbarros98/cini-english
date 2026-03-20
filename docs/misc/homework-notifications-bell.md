# Notificações do sininho (mensagens de tarefas)

## Objetivo
Avisar o professor (dono da conta e professor parceiro) quando um aluno enviar uma mensagem em uma tarefa (homework), exibindo um contador (“badge”) e uma lista curta no topo do sistema (sininho).

Ao abrir a conversa do aluno, as mensagens do aluno devem passar para o estado “lida”, zerando o contador na próxima atualização.

## O que foi implementado

### 1. Persistência do estado “lida”
Foi criado o modelo:
- `StudentHomeworkMessageRead` (`core/models.py`)

Ele registra, por professor (`user`), quais mensagens (`StudentHomeworkMessage`) já foram lidas, com `unique_together(message, user)` para evitar duplicidade.

Migração:
- `core/migrations/0048_studenthomeworkmessageread.py`

### 2. Marcar como lida ao abrir conversas do aluno
Quando o professor faz:
- `GET /api/student-homeworks/?student=<id>`

O `StudentHomeworkViewSet.list()` (em `core/views.py`) marca como “lida” todas as mensagens do **aluno** (`sender=student`) relacionadas aos homeworks daquele aluno que ainda não estavam registradas como lidas por aquele professor.

Observações:
- Apenas mensagens enviadas pelo **aluno** são marcadas como lidas.
- Mensagens enviadas pelo **professor** não entram nessa contagem.

### 3. Endpoint para alimentar o sininho (contador + lista)
Foi criado o endpoint:
- `GET /api/dashboard/unread-homework-messages/` (`core/views.py`)

Ele retorna:
- `unread_count`: quantidade de mensagens do aluno ainda não lidas
- `items`: lista curta (até 8) com:
  - `message_id`
  - `student_id`
  - `student_name`
  - `homework_id`
  - `homework_title`
  - `preview` (preview truncado)
  - `created_at`
  - `url` (link para `/alunos/<student_id>/`)

Permissões:
- Filtra mensagens pelos mesmos critérios de acesso já usados nas telas do professor.
- Ou seja: o professor vê apenas mensagens dos alunos que ele pode acessar (dono/parceiro/admin conforme regra já existente no sistema).

Rota:
- adicionada em `core/urls.py` com `name="dashboard-unread-homework-messages"`.

### 4. Widget do sininho no topo (com polling)
Foi adicionado um widget com sininho + badge + dropdown no partial:
- `frontend/templates/_mobile_nav.html`

O widget:
- Faz polling (fetch) a cada ~30s no endpoint `/api/dashboard/unread-homework-messages/`
- Atualiza o badge e a lista no dropdown
- Exibe estado “vazio” quando não há novas mensagens

Segurança:
- O `preview`, `student_name` e títulos são escapados no JS (`escapeHtml`) antes de renderizar.

Estilos:
- `core/static/styles.css` (classes `.hw-bell-widget`, `.hw-bell-btn`, `.hw-bell-dropdown`, etc.)

## Endpoints relevantes (referência rápida)
- Envio do aluno (público):
  - `POST /api/public/area-aluno/<token>/homeworks/<homework_id>/comment/`
- Envio do professor:
  - `POST /api/student-homeworks/<homework_id>/messages/`
- Sininho (notificações):
  - `GET /api/dashboard/unread-homework-messages/`
- Marcar como lida ao abrir conversa:
  - `GET /api/student-homeworks/?student=<id>`

## Como testar (manual)
1. Logar como professor (owner) e como professor parceiro (partner).
2. Enviar uma mensagem do aluno na área pública (uma tarefa).
3. Verificar no UI:
   - o badge do sininho aumenta
   - o item aparece na lista do dropdown
4. Abrir a conversa do aluno (`/alunos/<id>/`).
5. Voltar para o sininho e esperar a próxima atualização (~30s):
   - o contador deve zerar (ou reduzir conforme novas mensagens).

