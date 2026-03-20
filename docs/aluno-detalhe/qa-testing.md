# Testing guide: **Aluno detalhe** (`aluno_detalhe`)

Documentation for QA and developers on how to test the student detail page and related flows.

---

## 1. Overview

**Aluno detalhe** is the per-student “ficha” page: single place to see KPIs, resumo, materiais, homework, calendário, nota do professor, share link, and actions (editar aluno, atribuir HW, adicionar material).

| Item | Description |
|------|-------------|
| **Primary URL** | `/alunos/<student_id>/` (dynamic; requires login + subscription) |
| **View** | `AlunoDetalheView` — loads one `Student` the user is allowed to see |
| **Template** | `frontend/templates/aluno_detalhe.html` |
| **Main APIs used** | `GET/PATCH /api/students/<id>/`, `GET/POST/PATCH/DELETE /api/student-homeworks/`, `POST /api/students/<id>/materials/`, `GET /api/lessons/?student=<id>` |

**Teacher (account owner)** sees full UI including **Editar**, salvar nota, homework, materiais, etc.

**Partner teacher** sees the ficha for assigned students but **without** the **Editar** button and edit modal (read-only alignment with the main Alunos screen).

---

## 2. Prerequisites

Before running tests:

1. **Environment**
   - App running (e.g. `python manage.py runserver`).
   - Database migrated; at least one **teacher** user with active subscription (or trial).

2. **Data**
   - At least one **Student** belonging to that teacher.
   - Optional: lessons (for KPIs/calendário), `StudentHomework` rows (for homework tab/KPI), `LessonPlan` + attachments (for materiais).

3. **Access**
   - Log in as **teacher** (owner).
   - Open **Alunos** (`/alunos/`), pick a student, open the detail link (or go directly to `/alunos/<id>/`).

4. **Browsers**
   - Prefer Chrome or Edge for devtools (Network tab useful for API errors).

5. **Optional second persona**
   - Partner teacher account assigned to a student — to validate restricted UI.

---

## 3. Happy path test cases

### HP-1 — Open student detail and verify header & KPIs

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | Log in as teacher | Dashboard / home loads |
| 2 | Go to `/alunos/`, click a student to open detail (or `/alunos/<id>/`) | Page loads with correct **student name**, plan, status badge, phone |
| 3 | Check KPI row | **Aulas realizadas** / **Próxima aula** / **Financeiro** match data; **HOMEWORK** shows real `%` and “X de Y concluídos”, or “Nenhum homework” if none |

---

### HP-2 — Nota do professor (save)

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | Tab **Resumo** → find “Nota do professor” | Textarea shows current `teacher_notes` (or empty) |
| 2 | Edit text → **Salvar** | Toast: success message; after refresh, text persists |

---

### HP-3 — Homework: list, assign, feedback, status

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | Open tab **Homework** | List loads (or empty state) |
| 2 | **Atribuir HW** → fill title (and optional fields) → assign | New card appears; tab count updates |
| 3 | Expand card → type feedback → **Salvar feedback** | Toast confirms; feedback persists after reload |
| 4 | **Marcar Concluído** / **Marcar Pendente** | Status and badge update; toast optional |
| 5 | Reload page | KPI homework and tab data stay consistent |

---

### HP-4 — Materiais (modal + upload)

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | Tab **Materiais** → **Adicionar material** | Modal opens with Título, Tipo, Data, Escolher arquivo |
| 2 | Fill title, date, pick allowed file → **Enviar material** | Toast success → page reloads → file appears in list |
| 3 | Use type filters (PDF, etc.) | List filters correctly |

---

### HP-5 — Editar aluno (modal)

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | Click **Editar** | Modal opens; fields load from API (no mock names) |
| 2 | Change name, phone, plan fields, etc. → **Salvar alterações** | Toast success → full reload → hero and data updated |
| 3 | Compare same student on `/alunos/` side editor | Values match the same backend record |

---

### HP-6 — Área do aluno (share modal)

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | **Área do Aluno** | Modal opens with share URL |
| 2 | **Copiar link** | Toast “Link copiado!” (or equivalent) |

*(Exact share/token behaviour depends on backend implementation.)*

---

## 4. Edge cases

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| E-1 | Student with **zero** homework | Open detail of student with no HW | KPI shows no fake 78%; copy like “Nenhum homework atribuído” / neutral engajamento |
| E-2 | **Large** homework list | Many HW items | List scrolls; filters work; no browser freeze |
| E-3 | **Partner** teacher | Log in as partner → open assigned student | **Editar** hidden; rest of ficha usable per permissions |
| E-4 | Material **> 10 MB** | Modal upload | Error toast / message; no silent failure |
| E-5 | **Wrong file type** for material | Upload disallowed extension | API error surfaced in toast |
| E-6 | Clear **professor atribuído** in edit modal (if select exists) | Save | `assigned_teacher` cleared on server; list Alunos reflects it |
| E-7 | **Nível** “Não informado” | Save in edit modal | Level empty/null accepted |

---

## 5. Error scenarios

| ID | Scenario | How to trigger | Expected |
|----|----------|----------------|----------|
| ERR-1 | **Unauthenticated** | Open `/alunos/<id>/` logged out | Redirect to login |
| ERR-2 | **No subscription** | User without active sub | Redirect (e.g. planos) |
| ERR-3 | **Foreign student ID** | `/alunos/999999/` (not yours) | 404 |
| ERR-4 | **API failure** on save nota | Simulate offline or block `/api/students/` in DevTools | Toast or message indicates error |
| ERR-5 | **CSRF** | Rare in normal use; broken cookies | 403 on POST/PATCH; user sees error feedback |
| ERR-6 | Edit modal load fails | Invalid session mid-session | Error line in modal; user can close and retry |

---

## 6. Step-by-step templates (copy for tickets)

Use this structure when documenting a run:

```text
Test ID: HP-x / E-x / ERR-x
Date:
Tester:
Browser + version:
User role: teacher / partner

Steps:
1. ...
2. ...

Actual result:
Expected result:
Pass / Fail

Screenshots: (attach)
Network: (status code + endpoint if API)
Console errors: (paste if any)
```

---

## 7. How to report bugs

1. **Title** — Short, e.g. “Aluno detalhe: homework KPI shows 78% with 0 HW”.
2. **Environment** — URL, user type, student id (if not sensitive), browser.
3. **Reproduction** — Numbered steps from a known state (fresh login, which tab).
4. **Expected vs actual** — One sentence each.
5. **Evidence** — Screenshot or short screen recording; for API issues: **Network** tab (method, URL, status, response body).
6. **Severity suggestion**  
   - **Blocker** — Cannot save critical data or security issue.  
   - **High** — Wrong data shown (e.g. mock KPI), data loss.  
   - **Medium** — Missing toast, confusing UX, partner sees edit.  
   - **Low** — Cosmetic, typo.
7. **Where in code** (optional) — e.g. `aluno_detalhe.html`, `AlunoDetalheView`, `upload_student_material`.

**Where to file** — Your team’s issue tracker (GitHub Issues, Jira, etc.); tag **qa**, **aluno-detalhe**, **frontend** or **backend** as appropriate.

---

## 8. Legacy / demo route

`GET /aluno-detalhe/` may still render a **static demo** template without a real `student_id`. **Production testing should focus on** `/alunos/<student_id>/`.

---

## 9. Quick smoke checklist (5 min)

- [ ] `/alunos/<id>/` loads for owner  
- [ ] Homework KPI matches list tab  
- [ ] Salvar nota → toast + persist  
- [ ] Salvar feedback HW → toast + persist  
- [ ] Adicionar material (modal) → file appears  
- [ ] Editar aluno → save → header updates  
- [ ] Partner: no **Editar** on assigned student  

---

*Last aligned with: dynamic `AlunoDetalheView`, homework API, material modal, edit modal, toast behaviour.*
