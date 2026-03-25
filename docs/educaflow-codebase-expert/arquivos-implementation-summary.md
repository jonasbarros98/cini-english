# Arquivos (replacement for Tarefas) — implementation summary

**Reference date:** 2026-03-25 (implementation in the `Cini English` / EducaflowOne repository)  
**Purpose:** Let another AI or a human reviewer understand **what was shipped** (backend + frontend), **where it lives in the codebase**, and **what to double-check** — without duplicating the full product spec in `arquivos-feature-plan.md`.

---

## 1. Delivered scope

| Area | Change |
|------|--------|
| **Product** | **Arquivos** page (`/arquivos/`) — teacher-owned library (files + links), storage usage bar, search, filters, tags, CRUD, and **send to student** (creates a **copy** as `StudentMaterial`). |
| **Removal** | **Tarefas** feature: `Task` model, `/api/tasks/` API, `tasks_v2` template, `tasks-v2` / `tarefas-v2` routes, `tasks_open` count in dashboard summary. |
| **Navigation** | Sidebar “Tarefas” entries replaced with “Arquivos” across internal templates; dashboard quick action updated. |
| **Plan alignment** | Tier limits via `Subscription.get_arquivos_limits()` + trial fallback; allowed extensions; send-to-student uses **byte copy** (no shared `FileField` path). |
| **Spec correction** | Send-to-student uses **`AlunoDetalheView().get_queryset_students()`** (same rule as `upload_student_material`), not a non-existent `StudentViewSet` helper. |

---

## 2. Backend (Django / DRF)

### 2.1 Models & migration

- **Removed:** `Task` from `core/models.py`.
- **Added:** `TeacherMaterial` in `core/models.py` (after `StudentMaterial`): `TYPE_FILE` / `TYPE_LINK`, `upload_to="teacher_materials/%Y/%m/"`, `file_size`, `tags`, etc.
- **Added on `Subscription`:** `get_arquivos_limits()` — Basic / Premium / Platinum per `arquivos-feature-plan.md`.
- **Single migration:** `core/migrations/0054_remove_task_add_teacher_material.py`  
  - `CreateModel(TeacherMaterial)` + `DeleteModel(Task)`.

### 2.2 Constants & helpers (`core/views.py`)

- `ARQUIVOS_LIMITS_TRIAL` — limits when there is no active subscription (Basic-equivalent).
- `TEACHER_MATERIAL_ALLOWED_EXTENSIONS` — allowed file extensions set.
- `_get_arquivos_limits(user)` — active tier or trial.
- `_arquivos_forbidden_if_partner(request)` — **403** on all Arquivos APIs; template **redirect** for partner teachers (same product rule as hiding the nav item).

### 2.3 REST API (routes in `core/urls.py`)

| Method | URL | Handler | Notes |
|--------|-----|---------|--------|
| GET | `/api/arquivos/storage-info/` | `arquivos_storage_info` | Aggregated usage + limits. |
| GET | `/api/arquivos/` | `list_teacher_materials` | Query: `type`, `tag`, `q`. |
| POST | `/api/arquivos/upload/` | `upload_teacher_material` | Multipart; `@parser_classes([MultiPartParser, FormParser, JSONParser])`; quota & extension checks. |
| POST | `/api/arquivos/<id>/` | `update_teacher_material` | Title, description, tags, URL (links only). |
| POST | `/api/arquivos/<id>/delete/` | `delete_teacher_material` | Deletes underlying file when present. |
| POST | `/api/arquivos/<id>/send-to-student/` | `send_teacher_material_to_student` | JSON: `student_id`, `material_date`, optional `title`; copy via `ContentFile`. |
| GET | `/api/arquivos/<id>/download/` | `download_teacher_material_file` | **Authenticated** file streaming; needed when `DEBUG=False` (no reliable public `/media/`). |

**Removed:** `router.register(r"tasks", TaskViewSet)` and `TaskViewSet` itself.

**Decorator import:** `parser_classes` from `rest_framework.decorators` (fixes missing-name errors).

### 2.4 Serializer (`core/serializers.py`)

- Removed `Task` / `TaskSerializer`.
- Added `TeacherMaterial` + `TeacherMaterialSerializer`.
- **`file_url`** resolves to **`reverse("api-arquivos-download", ...)`** + `request.build_absolute_uri`, not raw `/media/...`, so it works with WhiteNoise and non-debug setups.

### 2.5 Admin (`core/admin.py`)

- Removed `Task` / `TaskAdmin`.
- Registered `TeacherMaterialAdmin`.

### 2.6 Dashboard API

- In `dashboard_summary_view`: removed `Task` counting block and `tasks_open` from `month_summary`.

### 2.7 `view-tasks` redirects

- `HomeView` & `DashboardView`: `?view=view-tasks` redirects to named route **`arquivos`** (no longer `tasks-v2`).

### 2.8 Students (optional filter)

- `StudentViewSet.get_queryset`: if `?status=...` is present, filters `Student.status` (used by Arquivos UI to fill the select with `status=active`).

---

## 3. Frontend

### 3.1 New page

- **`frontend/templates/arquivos.html`** — same shell as other app pages (`styles.css`, sidebar, `_mobile_nav.html`); dedicated UI: storage bar, card grid, modals (XHR upload progress, link, edit, send, delete), Lucide, toasts; `fetch` with CSRF.

### 3.2 Removed page

- **`frontend/templates/tasks_v2.html`** — **deleted**.

### 3.3 Page routes (`core/urls.py`)

- Removed: `tarefas-v2/` (TemplateView), `tasks-v2/` (`TasksV2View`).
- Added: `arquivos/` → `ArquivosView` (`name=arquivos`).
- Removed class `TasksV2View` from `core/views.py`.

### 3.4 Navigation & dashboard

Templates updated (pattern: `/arquivos/`, 📁, title **Arquivos**, subtitle **Sua biblioteca de materiais** — Portuguese UI copy unchanged), including:

- `frontend/templates/index.html`
- `frontend/templates/dashboard_home.html` — also removed Pendências “open tasks” badge + JS reading `tasks_open`; `data-go="arquivos"` + `go('arquivos')` for the quick action “Biblioteca de arquivos”.
- `frontend/templates/alunos_new.html`, `aluno_detalhe.html`, `calendar_new.html`, `planning_list.html`, `finance_refatorado.html`, `tickets.html`, `tutorial.html`, `perfil_user.html`, `planos.html`

### 3.5 Legacy script (`index` + `loadInitialData`)

- **`core/static/script.js`** & **`staticfiles/script.js`:** `loadTasks()` is a no-op with a comment (avoids calls to removed `/tasks/`).

---

## 4. Post-implementation fixes

| Issue | Fix |
|--------|-----|
| Download 404 with `DEBUG=False` | `GET /api/arquivos/<id>/download/` + serializer `file_url` pointing to it. |
| `NameError: parser_classes` | Import `parser_classes` in `core/views.py`. |
| Messy dashboard layout | Root cause: **incomplete static collection** (logo 404 → overlapping `alt` text). Run `collectstatic`; harden `.brand-icon` in `core/static/styles.css`. |
| Static settings | Comment + optional `DJANGO_STATICFILES_SIMPLE` for local non-manifest storage; WhiteNoise manifest remains default. |
| `_welcome_modal.html` | Font `<link>` in `<body>` replaced with `@import` inside `<style>`. |

---

## 5. Review checklist (for the other AI)

1. **Migrations:** `0054` applied everywhere; backup if any `Task` rows needed for history (usually feature removal only).
2. **Production:** CI/CD runs `collectstatic`; `CompressedManifestStaticFilesStorage` matches `staticfiles.json`.
3. **Storage:** Implementado `R2/S3` opcional para persistência real: quando `USE_R2_STORAGE=true`, o `DEFAULT_FILE_STORAGE` vai para `storages.backends.s3boto3.S3Boto3Storage` (Cloudflare R2 compatível) e `TeacherMaterial`/`StudentMaterial` gravam fora do container; quando `false`, continua usando `MEDIA_ROOT` local.
4. **Security:** Only the material owner hits download/API; partners blocked.
5. **Student copy:** `send-to-student` does **not** FK back to `TeacherMaterial` — one-way copy per spec.
6. **Regression:** No remaining `/tasks-v2/` or `/api/tasks/` in critical paths (grep the repo).
7. **Limits:** `get_arquivos_limits()` and `ARQUIVOS_LIMITS_TRIAL` match business rules.

---

## 6. Cross-reference

- Full product plan & phases: **`arquivos-feature-plan.md`** (same folder).
- **This file:** actual implementation + follow-up technical decisions.

---

*For human or AI review; update if further commits change behavior after the reference date.*
