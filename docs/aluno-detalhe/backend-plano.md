# Plano de integração backend — tela de detalhe do aluno

Objetivo: trocar dados mockados por dados reais **por partes**, só removendo mock quando a fonte estiver definida.

---

## Parte 1 — Aulas (Lesson) ✅ integrado

**Fonte:** modelo `Lesson` (FK para `Student`), campos `date`, `time`, `title`, `info`, `status`, `realized`.

**Integrar:**
- **KPI "Aulas realizadas"** → contagem de `Lesson` com `realized=True` (ou usar `student.lessons_done` já existente); "de X previstas" → `student.lessons_total`.
- **KPI "Próxima aula"** → próxima `Lesson` do aluno com `date >= hoje`, `realized=False`, `status != 'canceled'`, ordenada por data/hora.
- **Card "Próxima aula" (Resumo)** → mesmo objeto da próxima aula (data, título, horário).
- **Progresso do curso (Resumo)** → `student.lessons_done` / `student.lessons_total` (já existem no modelo).
- **Histórico de aulas (Resumo)** → últimas 5 `Lesson` do aluno, ordenadas por `-date`, `-time` (título, data, status realizado/cancelada).
- **Aba Calendário** → para o mês atual: dias com aula realizada vs agendada a partir de `Lesson` (realized + status).

**Mock removido apenas onde há dado real.** Se não houver próxima aula, mostrar "Nenhuma aula agendada". Se não houver histórico, mostrar lista vazia ou mensagem.

---

## Parte 2 — Situação financeira ✅ integrado

**Fonte:** modelo `Invoice` (FK para `Student`), `due_date`, `status` (pending, paid, overdue).

**Integrar:**
- **KPI "Financeiro"** → "Em dia" / "Pendente" / "Vencido" conforme existência de invoice pendente/vencido; "Venc. DD/MM" do próximo vencimento quando houver.

**Mock:** manter texto genérico quando o aluno não tiver invoices ou quando não houver vencimento próximo.

---

## Parte 3 — Nota do professor ✅ integrado

**Fonte:** campo `Student.teacher_notes` (TextField, blank=True).

**Estado:** migração 0043; serializer com `teacher_notes`; tela de detalhe carrega `student.teacher_notes` no textarea e salva via PATCH `/api/students/<id>/` ao clicar Salvar.

---

## Parte 4 — Materiais ✅ integrado

**Fonte:** `LessonPlanAttachment` (via `LessonPlan` do aluno).

**Estado:** na view são listados anexos com `LessonPlanAttachment.objects.filter(lesson_plan__student=student)`; contexto `materiais` com url, original_filename, file_type (pdf/audio/video/other), plan_date. Template: loop na aba Materiais com link para download; contagem na aba; filtro por tipo (Todos/PDF/Áudio/Vídeo) mantido; mensagem quando vazio.

---

## Parte 5 — Homework

**Fonte:** modelo `Task` é por **usuário**, não por aluno; não há "homework do aluno" no backend.

**Manter mock** até definir: novo modelo (ex. `StudentHomework`) ou estender `Task` com FK opcional para `Student` e tipo "homework". Só depois integrar lista, progresso e comentários.

---

## Ordem sugerida

1. **Parte 1 (Aulas)** ✅
2. **Parte 2 (Financeiro)** ✅ (usa FinancialEntry)
3. **Parte 3 (Nota do professor)** — próximo recomendado: campo + API + UI.
4. **Parte 4 (Materiais)** — opcional com LessonPlanAttachment.
5. **Parte 5 (Homework)** — só após definir modelo.

---

## Nível (CEFR) ✅

O campo `student.level` (A1–C2) já está no modelo e na lista de alunos. A tela de detalhe consome: badge no hero e card "NÍVEL ATUAL" no Resumo.

---

## Próximos passos de integração (sugestão)

| Prioridade | Item | O que fazer |
|------------|------|-------------|
| ~~1~~ | ~~Nota do professor~~ | ✅ Feito. |
| ~~2~~ | ~~Materiais~~ | ✅ Feito. |
| 3 | **Calendário por mês** | Hoje o calendário só tem dados reais do mês atual. Opcional: endpoint ou variável de contexto por mês (ex. `?month=2026-04`) para navegação entre meses com dados reais. |
| 4 | **Homework** | Definir modelo (ex. `StudentHomework` com FK para Student, ou estender `Task`); depois integrar lista, progresso e "Atribuir HW" na tela de detalhe. |
| 5 | **Engajamento / Dedicação** | Card "ENGAJAMENTO COM HW" e "DEDICAÇÃO" estão mockados; integrar quando houver fonte (ex. tasks por aluno ou métrica derivada). |
| 6 | **Meta de nível** | Opcional: campo `level_goal` (ex. B2) e `level_goal_deadline` em `Student` para exibir "Meta: B2 até Dezembro/2026" e barra de progresso no card de nível. |

Este arquivo será atualizado conforme as partes forem implementadas.
