# Aluno Detalhe — checklist para ficar utilizável

## Rota de teste

- **URL:** `http://localhost:8000/aluno-detalhe/`
- **Template:** `aluno_detalhe.html`
- **Contexto:** `is_partner_teacher: False` (sidebar completa). Para produção, use uma view que receba o ID do aluno e envie dados reais.

---

## O que já está no arquivo (design + interação)

- **Breadcrumb** — Alunos › Nome do aluno
- **Header** — avatar, nome, plano (B1→B2), status (badge ok/warn/bad), telefone; botões Editar, Área do Aluno, Atribuir HW
- **KPI row** — 4 cards: aulas realizadas, homework %, próxima aula, situação financeira
- **Tabs** — Resumo | Materiais | Homework | Calendário
- **Resumo** — próxima aula, grid de stats (progresso, engajamento HW, nível, dedicação), nota do professor (textarea + Salvar), histórico de aulas
- **Materiais** — filtro por tipo (Todos/PDF/Áudio/Vídeo/Link), botão Adicionar, lista com copiar link e remover
- **Homework** — filtro (Todos/Em andamento/Concluídos), botão Atribuir HW, cards expansíveis com descrição, progresso, comentário do aluno, área de feedback do professor, Remover / Marcar Concluído
- **Calendário** — navegação de mês, grade dinâmica (realizadas/agendadas/hoje), legenda, log de aulas, botão Registrar
- **Modais** — Compartilhar (link + Copiar, WhatsApp, E-mail, Gerar novo link); Editar aluno; Atribuir HW; Adicionar material; Registrar aula
- **Toast** — feedback de ações (link copiado, nota salva, etc.)
- **Scripts** — troca de abas, expandir HW, filtros de material e HW, abrir/fechar modais, copiar/compartilhar link, calendário dinâmico

---

## O que falta para produção (backend + integração)

1. **Rota com ID do aluno**  
   Ex.: `path("alunos/<int:student_id>/", AlunoDetalheView.as_view(), name="aluno-detalhe")`. A view deve carregar o aluno (e verificar se pertence ao professor logado / parceiro).

2. **Dados dinâmicos**  
   Trocar conteúdo estático (nome “Ana Clara”, aulas, materiais, HW, calendário) por dados do contexto: `student`, `lessons`, `materials`, `homework`, `next_lesson`, KPIs calculados, etc.

3. **APIs ou formulários reais**  
   - Salvar nota do professor (POST para API ou form com action).
   - Editar aluno: submit do modal para API de atualização do student.
   - Atribuir HW: criar registro de homework vinculado ao aluno.
   - Adicionar material: criar registro e, se houver arquivo, upload.
   - Registrar aula: criar/atualizar lesson.
   - Compartilhar: gerar/revogar token e retornar URL (ex.: `/area-aluno/<token>/`).

4. **Link “Compartilhar Área”**  
   O modal já mostra uma URL de exemplo. No backend: modelo ou tabela de “student share token” (aluno + token único + opcional expiração); view que gera/regenera o token e devolve a URL; rota pública `/aluno/<token>/` que renderiza `area_aluno.html` com dados só daquele aluno.

5. **Permissões**  
   Garantir que apenas o professor dono (ou parceiro autorizado) acesse `/alunos/<id>/` e os dados desse aluno.

6. **Breadcrumb dinâmico**  
   O link “Alunos” já aponta para `/alunos/`. O nome atual no breadcrumb deve vir do contexto (ex.: `student.name`).

7. **Ícones Lucide**  
   O script chama `lucide.createIcons()` no `DOMContentLoaded`. Se algum ícone não aparecer após carregar conteúdo via AJAX, chamar `lucide.createIcons()` de novo após inserir o HTML.

---

## Ajustes feitos agora

- **Rota:** `/aluno-detalhe/` → `TemplateView` com `aluno_detalhe.html` e `extra_context={"is_partner_teacher": False}`.
- **Typo:** `materaisList` → `materiaisList` (id do container e seletor no script).
- **Filtro de materiais:** uso de `.materiais-header .type-chip` em vez de `[data-type]` para ativar/desativar apenas os chips do header.

---

## Resumo

O arquivo está **pronto para teste visual e de fluxo** em `/aluno-detalhe/`. Para ficar **realmente utilizável** em produção, é preciso: rota com ID do aluno, view que carregue aluno + aulas + materiais + homework, APIs/formulários para salvar edições/HW/materiais/aulas e geração do link de compartilhar com token.
