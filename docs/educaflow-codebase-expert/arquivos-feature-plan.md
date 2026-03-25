# Arquivos Feature — Implementation Plan

**Date written:** 2026-03-25
**Target agent:** Cursor (no prior context — every reference below is fully qualified)
**Repository root:** assumed as `REPO_ROOT` in all paths below. Absolute path on the dev machine: `C:\users\jonas\OneDrive\Área de Trabalho\PYTHON\Cini English`

---

## 1. Overview

### What this feature is

"Arquivos" is a **teacher-owned personal file library** built into EducaflowOne. Each teacher stores their own work materials (PDFs, audio files, documents, images, links) in a central repository that is independent of any particular student. Think of it as the teacher's digital drawer — reusable materials they reach for every day.

### Why it replaces Tarefas

The current "Tarefas" feature is a generic Kanban board (`Task` model, `TaskViewSet`, `tasks_v2.html`) that was never adopted because the Planejamento module already handles academic scheduling. Removing it simplifies the product and frees a primary navigation slot for Arquivos, which addresses a real unmet need.

### Relationship to StudentMaterial

`StudentMaterial` (already in production) is student-scoped: a material is attached to a specific student and shown in the Área do Aluno. The new `TeacherMaterial` model is teacher-scoped. The bridge between them is a deliberate "send to student" action: the teacher picks a student, and a `StudentMaterial` record is created referencing (or copying) the `TeacherMaterial` file. No automatic linking happens.

---

## 2. Prerequisites — Persistent Storage

**This must be completed BEFORE the Arquivos feature goes live in production.** All existing file uploads (contracts, lesson plan attachments, student materials, profile photos) also benefit from this fix.

### Problem

`config/settings.py` line 213:
```python
MEDIA_ROOT = BASE_DIR / "media"
```
Railway's default deployment uses an ephemeral filesystem. Every redeploy wipes all uploaded files. This is already a latent bug for `contracts/`, `lesson_plan_attachments/`, `student_materials/`, and `profile_photos/`. Arquivos would make this business-critical.

### Recommended solution: `django-storages` + Cloudflare R2

Cloudflare R2 has an S3-compatible API and **zero egress fees**, making it preferable to AWS S3 for a cost-sensitive SaaS.

**Steps:**

1. Install dependencies:
   ```
   pip install django-storages[s3] boto3
   ```
   Add both to `requirements.txt`.

2. Create a Cloudflare R2 bucket named `educaflowone-media` (or similar). Generate an API token with Object Read & Write on that bucket.

3. Add to `config/settings.py` after line 213, replacing the `MEDIA_ROOT` block:
   ```python
   # Persistent media storage via Cloudflare R2 (S3-compatible)
   USE_R2_STORAGE = os.environ.get("USE_R2_STORAGE", "false").lower() == "true"

   if USE_R2_STORAGE:
       DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
       AWS_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
       AWS_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
       AWS_STORAGE_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "educaflowone-media")
       AWS_S3_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "")  # e.g. https://<account_id>.r2.cloudflarestorage.com
       AWS_S3_REGION_NAME = "auto"
       AWS_DEFAULT_ACL = None
       AWS_S3_FILE_OVERWRITE = False
       AWS_QUERYSTRING_AUTH = True  # signed URLs; set False if bucket is public
       AWS_S3_SIGNATURE_VERSION = "s3v4"
       MEDIA_URL = os.environ.get("R2_MEDIA_URL", f"https://{AWS_STORAGE_BUCKET_NAME}.r2.cloudflarestorage.com/")
   else:
       MEDIA_ROOT = BASE_DIR / "media"
       MEDIA_URL = "/media/"
   ```

4. Set these Railway environment variables:
   - `USE_R2_STORAGE=true`
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_BUCKET_NAME`
   - `R2_ENDPOINT_URL`
   - `R2_MEDIA_URL` (optional public domain, e.g. a custom Cloudflare domain)

5. Migrate existing files from the ephemeral Railway filesystem to R2 using `rclone` or a one-off management command **before** removing the old `MEDIA_ROOT` path from settings.

### Alternative: Railway Persistent Volume

If R2 integration is too complex, Railway supports attaching a Persistent Volume to a service. Set the mount path to `/app/media` and update `MEDIA_ROOT`:
```python
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media")))
```
Set the `MEDIA_ROOT` environment variable to `/app/media` in the Railway service. This is simpler but has a per-GB cost and no CDN edge caching.

---

## 3. Phase 1 — Remove Tarefas

Remove every trace of the `Task` model and its supporting code. This must be done in one atomic PR with the migration.

### 3.1 `core/models.py`

**Lines 234–276** define the `Task` model:
```python
class Task(models.Model):
    STATUS_CHOICES = [...]
    title = ...
    status = ...
    tags = ...
    date = ...
    due_date = ...
    notes = ...
    user = ...
    created_at = ...
    updated_at = ...
```
**Delete the entire `Task` class (lines 234–276 inclusive).**

### 3.2 `core/serializers.py`

- **Line 3:** Remove `Task` from the import:
  ```python
  # Before:
  from .models import Student, Lesson, Task, Invoice, ...
  # After:
  from .models import Student, Lesson, Invoice, ...
  ```
- **Lines 144–163:** Delete the entire `TaskSerializer` class.

### 3.3 `core/views.py`

- **Line 36:** Remove `Task` from the model import line:
  ```python
  # Before:
  from .models import Student, Lesson, Task, StudentHomework, ...
  # After:
  from .models import Student, Lesson, StudentHomework, ...
  ```
- **Line 37:** Remove `TaskSerializer` from the serializer import line:
  ```python
  # Before:
  from .serializers import StudentSerializer, LessonSerializer, TaskSerializer, ...
  # After:
  from .serializers import StudentSerializer, LessonSerializer, ...
  ```
- **Lines 433–465:** Delete the entire `TaskViewSet` class.
- **Lines 1423–1449:** Delete the entire `TasksV2View` class.
- **Lines 5001–5004:** In `dashboard_summary_view`, delete the `tasks_open` query block:
  ```python
  # Delete these 4 lines:
  tasks_open = Task.objects.filter(
      user_id__in=user_ids,
      status__in=['todo', 'doing']
  ).count()
  ```
- **Line 5049:** In the `month_summary` dict returned by `dashboard_summary_view`, delete the key:
  ```python
  'tasks_open': tasks_open,   # DELETE THIS LINE
  ```

### 3.4 `core/urls.py`

- **Line 6:** Remove `TaskViewSet` from the view imports:
  ```python
  # Before:
  from .views import (
      StudentViewSet, LessonViewSet, TaskViewSet, HomeView, ...
      ...
      TasksV2View, AdminPanelView, ...
  )
  # After: remove TaskViewSet and TasksV2View from both lines
  ```
- **Line 39:** Delete the router registration:
  ```python
  router.register(r"tasks", TaskViewSet, basename="task")  # DELETE
  ```
- **Line 49:** Delete the tarefas-v2 TemplateView route:
  ```python
  path("tarefas-v2/", TemplateView.as_view(template_name="tasks_v2.html"), name="tasks-v2"),  # DELETE
  ```
- **Line 74:** Delete the tasks-v2 TasksV2View route:
  ```python
  path("tasks-v2/", TasksV2View.as_view(), name="tasks-v2"),  # DELETE
  ```

### 3.5 `core/admin.py`

- **Line 2:** Remove `Task` from the import:
  ```python
  from .models import Student, Lesson, Task, Invoice, ...
  # → remove Task
  ```
- **Lines 17–21:** Delete the `TaskAdmin` registration:
  ```python
  @admin.register(Task)
  class TaskAdmin(admin.ModelAdmin):
      list_display = ("title", "status", "user", "date", "due_date")
      list_filter = ("status", "user", "date")
      search_fields = ("title", "tags", "user__username")
  ```

### 3.6 `frontend/templates/index.html`

**Lines 96–102** (inside `{% if not is_partner_teacher %}` block):
```html
<a href="/tasks-v2/" class="nav-item">
  <span class="nav-emoji">✅</span>
  <div>
    <p class="nav-title">Tarefas</p>
    <p class="nav-subtitle">Planejamento rápido</p>
  </div>
</a>
```
Replace this `<a>` block with the Arquivos link (see Phase 5 for the exact replacement markup).

### 3.7 `frontend/templates/dashboard_home.html`

Four locations to change:

**A) Sidebar nav — lines 730–736** (inside `{% if not is_partner_teacher %}` block):
```html
<a href="/tasks-v2/" class="nav-item">
  <span class="nav-emoji">✅</span>
  <div>
    <p class="nav-title">Tarefas</p>
    <p class="nav-subtitle">Planejamento rápido</p>
  </div>
</a>
```
Replace with Arquivos nav link (see Phase 5).

**B) Month summary "Pendencias" badge — line 1089:**
```html
<span class="badge warn" id="monthTasksOpen">0 tarefas</span>
```
Remove this `<span>` element entirely. The "reschedules" span on line 1090 stays.

**C) JavaScript: tasks_open data binding — lines 1352–1358:**
```javascript
const monthTasksOpenEl = document.getElementById("monthTasksOpen");
// ...
if (monthTasksOpenEl) {
  const tasksOpen = monthSummary.tasks_open || 0;
  monthTasksOpenEl.textContent = `${tasksOpen} tarefa${tasksOpen !== 1 ? 's' : ''}`;
}
```
Delete this entire `if (monthTasksOpenEl)` block.

**D) JavaScript: error fallback — line 1424:**
```javascript
if (monthTasksOpenEl) monthTasksOpenEl.textContent = "0 tarefas";
```
Delete this line.

**E) Quick-action navigation — lines 1466–1469:**
```javascript
if (where === 'tasks') {
  window.location.href = '/tasks-v2/';
  return;
}
```
Replace with:
```javascript
if (where === 'arquivos') {
  window.location.href = '/arquivos/';
  return;
}
```
(Only needed if there is a quick-action button that pointed to tasks; check the dashboard for any `data-navigate="tasks"` button and update its value to `"arquivos"` as well.)

### 3.8 `frontend/templates/tasks_v2.html`

Delete this file entirely.

### 3.9 Migration

Generate the migration to drop the `Task` table:
```bash
python manage.py makemigrations core --name="remove_task_model"
```
Verify the migration only contains `DeleteModel` for `Task`. Commit and apply in production.

The migration number will be `0054_remove_task_model.py` (current latest is `0053_userprofile_google_fields.py`).

---

## 4. Phase 2 — TeacherMaterial Model

### 4.1 Model definition

Add the following class to `core/models.py`, placed **after the `StudentMaterial` class** (currently ending at line 684), before the `UserProfile` class (currently at line 687):

```python
class TeacherMaterial(models.Model):
    """
    Biblioteca pessoal de materiais do professor (Arquivos).
    Independente de alunos. Pode ser compartilhado com um aluno via ação 'Enviar para aluno',
    que cria um StudentMaterial derivado.
    """

    TYPE_FILE = "file"
    TYPE_LINK = "link"
    TYPE_CHOICES = [
        (TYPE_FILE, "Arquivo"),
        (TYPE_LINK, "Link"),
    ]

    # --- Relationships ---
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="teacher_materials",
        help_text="Professor dono deste material",
    )

    # --- Content ---
    title = models.CharField(
        max_length=200,
        help_text="Nome/título do material exibido na biblioteca",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Descrição ou observação interna (não visível ao aluno)",
    )
    material_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default=TYPE_FILE,
    )
    file = models.FileField(
        upload_to="teacher_materials/%Y/%m/",
        blank=True,
        null=True,
        help_text="Arquivo (preenchido quando material_type='file')",
    )
    external_url = models.URLField(
        blank=True,
        default="",
        help_text="URL externa (preenchida quando material_type='link')",
    )
    file_size = models.PositiveIntegerField(
        default=0,
        help_text="Tamanho do arquivo em bytes (0 para links)",
    )

    # --- Organisation ---
    tags = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text="Tags de organização separadas por vírgula (ex: gramática,B2,speaking)",
    )

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Material do Professor"
        verbose_name_plural = "Materiais do Professor"

    def __str__(self):
        return f"{self.user.username} — {self.title}"

    def get_file_size_display(self):
        """Formata o tamanho do arquivo de forma legível."""
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
```

### 4.2 Field constraints and limits (enforced in the view, not in the model)

These are the business rules the viewset must enforce:

| Limit | Basic | Premium | Platinum |
|---|---|---|---|
| Max file size (per upload) | 10 MB | 20 MB | 50 MB |
| Max total storage per teacher | 100 MB | 500 MB | 2 GB |
| Max number of files | 50 | 200 | unlimited |
| Allowed extensions | pdf, doc, docx, xls, xlsx, ppt, pptx, mp3, wav, m4a, ogg, aac, mp4, webm, jpg, jpeg, png, gif, webp, txt | same | same |
| Links | unlimited | unlimited | unlimited |

Links are free (no storage consumed). File count includes only `material_type='file'` records.

Add a `get_arquivos_limits` method to the `Subscription` model in `core/models.py` (after the `get_max_partner_teachers` method at line 948):

```python
def get_arquivos_limits(self):
    """Retorna os limites de Arquivos para este tier."""
    limits = {
        self.TIER_BASIC: {
            "max_file_size": 10 * 1024 * 1024,      # 10 MB
            "max_total_bytes": 100 * 1024 * 1024,    # 100 MB
            "max_files": 50,
        },
        self.TIER_PREMIUM: {
            "max_file_size": 20 * 1024 * 1024,       # 20 MB
            "max_total_bytes": 500 * 1024 * 1024,    # 500 MB
            "max_files": 200,
        },
        self.TIER_PLATINUM: {
            "max_file_size": 50 * 1024 * 1024,       # 50 MB
            "max_total_bytes": 2 * 1024 * 1024 * 1024,  # 2 GB
            "max_files": None,  # unlimited
        },
    }
    return limits.get(self.tier, limits[self.TIER_BASIC])
```

Also add a fallback constant at the top of `core/views.py` (near other settings constants) for users without a subscription (trial):

```python
ARQUIVOS_LIMITS_TRIAL = {
    "max_file_size": 10 * 1024 * 1024,
    "max_total_bytes": 100 * 1024 * 1024,
    "max_files": 50,
}
```

### 4.3 Allowed file extensions

Define this list as a module-level constant in `core/views.py` (near the top, after imports):

```python
TEACHER_MATERIAL_ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".wav", ".m4a", ".ogg", ".aac",
    ".mp4", ".webm",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".txt",
}
```

### 4.4 Migration

```bash
python manage.py makemigrations core --name="add_teacher_material"
```

This will be migration `0055_add_teacher_material.py`.

### 4.5 Register in admin

Add to `core/admin.py`:

```python
from .models import TeacherMaterial  # add to existing import line

@admin.register(TeacherMaterial)
class TeacherMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "material_type", "file_size_display", "created_at")
    list_filter = ("material_type", "user", "created_at")
    search_fields = ("title", "tags", "user__username")
    readonly_fields = ("file_size", "created_at", "updated_at")
    date_hierarchy = "created_at"

    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = "Tamanho"
```

---

## 5. Phase 3 — Backend API

### 5.1 TeacherMaterialSerializer

Add to `core/serializers.py` (after the `StudentHomeworkSerializer` class, which ends around line 220):

```python
from .models import TeacherMaterial  # add to existing models import line at line 3

class TeacherMaterialSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = TeacherMaterial
        fields = [
            "id",
            "user",
            "title",
            "description",
            "material_type",
            "file",
            "file_url",
            "external_url",
            "file_size",
            "file_size_display",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "file_url", "file_size", "file_size_display", "created_at", "updated_at"]

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_size_display(self, obj):
        return obj.get_file_size_display()
```

### 5.2 URL routes

Add to `core/urls.py`:

**Import additions** — add to the imports block at the top:
```python
ArquivosView,
upload_teacher_material,
delete_teacher_material,
update_teacher_material,
list_teacher_materials,
send_teacher_material_to_student,
arquivos_storage_info,
```

**URL patterns** — add after the student material routes (around line 118):
```python
# Arquivos (biblioteca pessoal do professor)
path("arquivos/", ArquivosView.as_view(), name="arquivos"),
path("api/arquivos/", list_teacher_materials, name="api-arquivos-list"),
path("api/arquivos/upload/", upload_teacher_material, name="api-arquivos-upload"),
path("api/arquivos/<int:material_id>/", update_teacher_material, name="api-arquivos-update"),
path("api/arquivos/<int:material_id>/delete/", delete_teacher_material, name="api-arquivos-delete"),
path("api/arquivos/<int:material_id>/send-to-student/", send_teacher_material_to_student, name="api-arquivos-send-to-student"),
path("api/arquivos/storage-info/", arquivos_storage_info, name="api-arquivos-storage-info"),
```

### 5.3 View functions

Add all functions below to `core/views.py`. Place them in a clearly demarcated section after the existing student material views (currently ending around line 1189). Use this section header comment:

```python
# ==========================
# Arquivos (TeacherMaterial)
# ==========================
```

---

**`ArquivosView`** (page view):
```python
class ArquivosView(TemplateView):
    template_name = "arquivos.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            ctx["user_is_admin"] = profile.is_admin
            ctx["is_partner_teacher"] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except Exception:
            ctx["user_is_admin"] = False
            ctx["is_partner_teacher"] = False
        return ctx

    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect("login")
        if not _user_has_active_subscription(request.user):
            return redirect("planos")
        return super().dispatch(request, *args, **kwargs)
```

---

**`_get_arquivos_limits(user)`** (internal helper):
```python
def _get_arquivos_limits(user):
    """Returns the Arquivos storage/count limits for the given user's subscription tier."""
    try:
        sub = user.subscription
        if sub.is_active:
            return sub.get_arquivos_limits()
    except Exception:
        pass
    return ARQUIVOS_LIMITS_TRIAL
```

---

**`arquivos_storage_info`** (GET — returns current usage + limits):
```python
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def arquivos_storage_info(request):
    """
    GET /api/arquivos/storage-info/
    Returns current storage usage and limits for the authenticated teacher.
    Response: {
        "used_bytes": int,
        "used_display": str,
        "file_count": int,
        "limits": { "max_file_size": int, "max_total_bytes": int|null, "max_files": int|null }
    }
    """
    from .models import TeacherMaterial
    qs = TeacherMaterial.objects.filter(user=request.user, material_type=TeacherMaterial.TYPE_FILE)
    used_bytes = qs.aggregate(total=models.Sum("file_size"))["total"] or 0
    file_count = qs.count()
    limits = _get_arquivos_limits(request.user)

    def fmt(b):
        for unit in ["B", "KB", "MB", "GB"]:
            if b < 1024.0:
                return f"{b:.1f} {unit}"
            b /= 1024.0
        return f"{b:.1f} TB"

    return Response({
        "used_bytes": used_bytes,
        "used_display": fmt(used_bytes),
        "file_count": file_count,
        "limits": limits,
    })
```

---

**`list_teacher_materials`** (GET — list all materials):
```python
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_teacher_materials(request):
    """
    GET /api/arquivos/?type=file|link&tag=...&q=...
    Returns all TeacherMaterial records for the authenticated teacher.
    Optional query params:
      type: 'file' | 'link'  — filter by material_type
      tag:  string           — filter by tag (partial match)
      q:    string           — search in title and description
    """
    from .models import TeacherMaterial
    from .serializers import TeacherMaterialSerializer
    qs = TeacherMaterial.objects.filter(user=request.user)
    type_filter = request.query_params.get("type", "").strip()
    tag_filter = request.query_params.get("tag", "").strip()
    q = request.query_params.get("q", "").strip()
    if type_filter in (TeacherMaterial.TYPE_FILE, TeacherMaterial.TYPE_LINK):
        qs = qs.filter(material_type=type_filter)
    if tag_filter:
        qs = qs.filter(tags__icontains=tag_filter)
    if q:
        qs = qs.filter(models.Q(title__icontains=q) | models.Q(description__icontains=q))
    serializer = TeacherMaterialSerializer(qs, many=True, context={"request": request})
    return Response(serializer.data)
```

---

**`upload_teacher_material`** (POST — upload file or add link):
```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_teacher_material(request):
    """
    POST /api/arquivos/upload/
    Accepts multipart/form-data with:
      file          (for material_type='file')
      material_type 'file' | 'link'  (default: 'file')
      title         string (required; max 200 chars)
      description   string (optional)
      tags          comma-separated string (optional)
      external_url  string (required when material_type='link')
    Returns: { "ok": true, "material": { ...TeacherMaterialSerializer fields } }
    """
    from .models import TeacherMaterial
    from .serializers import TeacherMaterialSerializer

    material_type = (request.POST.get("material_type") or TeacherMaterial.TYPE_FILE).strip()
    title = (request.POST.get("title") or "").strip()[:200]
    description = (request.POST.get("description") or "").strip()
    tags = (request.POST.get("tags") or "").strip()[:300]
    external_url = (request.POST.get("external_url") or "").strip()

    limits = _get_arquivos_limits(request.user)

    # --- Handle LINK ---
    if material_type == TeacherMaterial.TYPE_LINK:
        if not external_url:
            return Response({"error": "Informe uma URL válida."}, status=status.HTTP_400_BAD_REQUEST)
        if not (external_url.startswith("http://") or external_url.startswith("https://")):
            return Response({"error": "URL deve começar com http:// ou https://"}, status=status.HTTP_400_BAD_REQUEST)
        if not title:
            title = external_url[:200]
        material = TeacherMaterial.objects.create(
            user=request.user,
            title=title,
            description=description,
            material_type=TeacherMaterial.TYPE_LINK,
            external_url=external_url,
            file_size=0,
            tags=tags,
        )
        return Response(
            {"ok": True, "material": TeacherMaterialSerializer(material, context={"request": request}).data},
            status=status.HTTP_201_CREATED,
        )

    # --- Handle FILE ---
    file = request.FILES.get("file")
    if not file:
        return Response({"error": "Arquivo não enviado."}, status=status.HTTP_400_BAD_REQUEST)

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in TEACHER_MATERIAL_ALLOWED_EXTENSIONS:
        return Response(
            {"error": f"Tipo de arquivo não permitido: {ext}. Use: PDF, Word, Excel, PowerPoint, áudio, vídeo, imagem ou TXT."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    max_file_size = limits["max_file_size"]
    if file.size > max_file_size:
        return Response(
            {"error": f"Arquivo muito grande. Máximo: {max_file_size // (1024*1024)} MB no seu plano."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Count and total storage checks
    existing_qs = TeacherMaterial.objects.filter(user=request.user, material_type=TeacherMaterial.TYPE_FILE)
    file_count = existing_qs.count()
    if limits["max_files"] is not None and file_count >= limits["max_files"]:
        return Response(
            {"error": f"Limite de {limits['max_files']} arquivos atingido no seu plano."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    used_bytes = existing_qs.aggregate(total=models.Sum("file_size"))["total"] or 0
    if limits["max_total_bytes"] is not None and (used_bytes + file.size) > limits["max_total_bytes"]:
        max_mb = limits["max_total_bytes"] // (1024 * 1024)
        return Response(
            {"error": f"Armazenamento cheio. Seu plano tem {max_mb} MB de Arquivos."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not title:
        title = file.name[:200]

    material = TeacherMaterial.objects.create(
        user=request.user,
        title=title,
        description=description,
        material_type=TeacherMaterial.TYPE_FILE,
        file=file,
        file_size=file.size,
        tags=tags,
    )
    return Response(
        {"ok": True, "material": TeacherMaterialSerializer(material, context={"request": request}).data},
        status=status.HTTP_201_CREATED,
    )
```

---

**`delete_teacher_material`** (POST — delete a material):
```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_teacher_material(request, material_id):
    """
    POST /api/arquivos/<material_id>/delete/
    Deletes the TeacherMaterial and its associated file (if any).
    Only the owner can delete.
    Returns: { "ok": true }
    """
    from .models import TeacherMaterial
    try:
        material = TeacherMaterial.objects.get(id=material_id, user=request.user)
    except TeacherMaterial.DoesNotExist:
        return Response({"error": "Material não encontrado."}, status=status.HTTP_404_NOT_FOUND)
    if material.file:
        material.file.delete(save=False)
    material.delete()
    return Response({"ok": True})
```

---

**`update_teacher_material`** (POST — update title, description, tags, or external_url):
```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_teacher_material(request, material_id):
    """
    POST /api/arquivos/<material_id>/
    Updates editable fields of a TeacherMaterial.
    Body (JSON or form-data):
      title        (optional)
      description  (optional)
      tags         (optional)
      external_url (optional; only for links)
    Returns: { "ok": true, "material": { ...TeacherMaterialSerializer fields } }
    """
    from .models import TeacherMaterial
    from .serializers import TeacherMaterialSerializer
    try:
        material = TeacherMaterial.objects.get(id=material_id, user=request.user)
    except TeacherMaterial.DoesNotExist:
        return Response({"error": "Material não encontrado."}, status=status.HTTP_404_NOT_FOUND)

    payload = request.data
    if "title" in payload:
        material.title = (payload["title"] or "").strip()[:200] or material.title
    if "description" in payload:
        material.description = (payload["description"] or "").strip()
    if "tags" in payload:
        material.tags = (payload["tags"] or "").strip()[:300]
    if "external_url" in payload and material.material_type == TeacherMaterial.TYPE_LINK:
        url = (payload["external_url"] or "").strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            return Response({"error": "URL inválida."}, status=status.HTTP_400_BAD_REQUEST)
        material.external_url = url

    material.save(update_fields=["title", "description", "tags", "external_url", "updated_at"])
    return Response(
        {"ok": True, "material": TeacherMaterialSerializer(material, context={"request": request}).data}
    )
```

---

**`send_teacher_material_to_student`** (POST — bridge action, see Phase 6 for full spec):
```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_teacher_material_to_student(request, material_id):
    """
    POST /api/arquivos/<material_id>/send-to-student/
    Body (JSON): { "student_id": int, "title": str (optional override), "material_date": "YYYY-MM-DD" (optional) }
    Creates a StudentMaterial entry from this TeacherMaterial.
    See Phase 6 for full field mapping.
    Returns: { "ok": true, "student_material_id": int }
    """
    # Implementation detailed in Phase 6.
    pass
```

---

## 6. Phase 4 — Arquivos Page (`arquivos.html`)

Create the file at `frontend/templates/arquivos.html`. Model the overall page structure on `frontend/templates/tasks_v2.html` (which uses the same `{% load static %}`, `styles.css`, and sidebar as the rest of the app) — but with entirely new content.

### 6.1 Page structure (HTML skeleton)

```
{% load static %}<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <!-- same <meta>, fonts, styles.css, lucide as other pages -->
  <title>Arquivos — EducaflowOne</title>
</head>
<body>
  <!-- shared sidebar (copy structure from index.html) -->
  <div id="sidebar">...</div>

  <main class="main-content">
    <!-- Page header -->
    <div class="page-header">
      <h1>Arquivos</h1>
      <p class="page-subtitle">Sua biblioteca de materiais</p>
      <!-- Storage usage bar -->
      <div id="storageBar">
        <span id="storageUsedLabel">carregando...</span>
        <div class="progress-bar"><div id="storageUsedBar" style="width:0%"></div></div>
      </div>
    </div>

    <!-- Toolbar: search + filter tabs + upload button -->
    <div class="toolbar">
      <input type="text" id="searchInput" placeholder="Buscar por título..." />
      <div class="filter-tabs">
        <button class="tab active" data-filter="all">Todos</button>
        <button class="tab" data-filter="file">Arquivos</button>
        <button class="tab" data-filter="link">Links</button>
      </div>
      <button id="btnAddLink" class="btn-secondary">+ Link</button>
      <button id="btnUpload" class="btn-primary">+ Arquivo</button>
    </div>

    <!-- Tag filter pills (dynamically rendered from tags in current materials) -->
    <div id="tagFilters"></div>

    <!-- Materials grid -->
    <div id="materialsGrid" class="materials-grid">
      <!-- Cards rendered by JS -->
    </div>

    <!-- Empty state -->
    <div id="emptyState" class="empty-state" hidden>
      <p>Nenhum material ainda. Clique em "+" para adicionar.</p>
    </div>
  </main>

  <!-- Upload modal -->
  <dialog id="uploadModal">
    <form id="uploadForm">
      <h2>Adicionar arquivo</h2>
      <label>Título <input type="text" name="title" maxlength="200" /></label>
      <label>Descrição <textarea name="description"></textarea></label>
      <label>Tags (separadas por vírgula) <input type="text" name="tags" maxlength="300" /></label>
      <label>Arquivo <input type="file" name="file" id="fileInput" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.mp3,.wav,.m4a,.ogg,.aac,.mp4,.webm,.jpg,.jpeg,.png,.gif,.webp,.txt" /></label>
      <div id="uploadProgress" hidden><progress id="uploadBar" value="0" max="100"></progress></div>
      <div class="modal-actions">
        <button type="button" id="cancelUpload">Cancelar</button>
        <button type="submit" id="submitUpload">Salvar</button>
      </div>
    </form>
  </dialog>

  <!-- Add link modal -->
  <dialog id="linkModal">
    <form id="linkForm">
      <h2>Adicionar link</h2>
      <label>URL <input type="url" name="external_url" required placeholder="https://..." /></label>
      <label>Título (opcional) <input type="text" name="title" maxlength="200" /></label>
      <label>Descrição <textarea name="description"></textarea></label>
      <label>Tags <input type="text" name="tags" maxlength="300" /></label>
      <div class="modal-actions">
        <button type="button" id="cancelLink">Cancelar</button>
        <button type="submit" id="submitLink">Salvar</button>
      </div>
    </form>
  </dialog>

  <!-- Edit modal (title, description, tags, external_url for links) -->
  <dialog id="editModal">
    <form id="editForm">
      <h2>Editar material</h2>
      <input type="hidden" name="material_id" />
      <input type="hidden" name="material_type" />
      <label>Título <input type="text" name="title" maxlength="200" /></label>
      <label>Descrição <textarea name="description"></textarea></label>
      <label>Tags <input type="text" name="tags" maxlength="300" /></label>
      <div id="editUrlRow">
        <label>URL <input type="url" name="external_url" /></label>
      </div>
      <div class="modal-actions">
        <button type="button" id="cancelEdit">Cancelar</button>
        <button type="submit" id="submitEdit">Salvar</button>
      </div>
    </form>
  </dialog>

  <!-- Send to student modal -->
  <dialog id="sendModal">
    <div>
      <h2>Enviar para aluno</h2>
      <input type="hidden" id="sendMaterialId" />
      <label>Aluno
        <select id="sendStudentSelect">
          <option value="">Selecionar aluno...</option>
          <!-- populated by JS from /api/students/ -->
        </select>
      </label>
      <label>Data de referência <input type="date" id="sendMaterialDate" /></label>
      <label>Título para o aluno (opcional)
        <input type="text" id="sendTitleOverride" maxlength="200" placeholder="Deixe em branco para usar o título original" />
      </label>
      <div class="modal-actions">
        <button type="button" id="cancelSend">Cancelar</button>
        <button type="button" id="confirmSend">Enviar</button>
      </div>
    </div>
  </dialog>

  <!-- Delete confirmation modal -->
  <dialog id="deleteModal">
    <div>
      <h2>Excluir material?</h2>
      <p id="deleteModalName"></p>
      <p class="warn">Esta ação não pode ser desfeita.</p>
      <input type="hidden" id="deleteMaterialId" />
      <div class="modal-actions">
        <button type="button" id="cancelDelete">Cancelar</button>
        <button type="button" id="confirmDelete" class="btn-danger">Excluir</button>
      </div>
    </div>
  </dialog>
</body>
</html>
```

### 6.2 Material card spec

Each card in `#materialsGrid` must display:

- File type icon (see icon mapping below)
- Title (truncated to 2 lines with `text-overflow: ellipsis`)
- Description (single line, muted, optional)
- Tag pills (grey, small)
- File size (for files) or domain name extracted from URL (for links)
- Date uploaded (`created_at` formatted as `DD/MM/YYYY`)
- Three action buttons: "Abrir/Baixar", "Enviar para aluno", "Editar", "Excluir"

**File type icon mapping** (use Lucide icons; same library as the rest of the app):
```
.pdf               → lucide:file-text (red accent)
.doc .docx         → lucide:file-text (blue accent)
.xls .xlsx         → lucide:table (green accent)
.ppt .pptx         → lucide:presentation (orange accent)
.mp3 .wav .m4a .ogg .aac → lucide:music (purple accent)
.mp4 .webm         → lucide:video (indigo accent)
.jpg .jpeg .png .gif .webp → lucide:image (pink accent)
.txt               → lucide:file (grey accent)
link               → lucide:link (blue accent)
```

### 6.3 JavaScript behaviour

All API calls use `fetch` with `getCookie("csrftoken")` in headers — same pattern as `dashboard_home.html` lines 1136–1143.

**On page load:**
1. Call `GET /api/arquivos/storage-info/` → render storage bar
2. Call `GET /api/arquivos/` → render all cards
3. Call `GET /api/students/?status=active` → populate `#sendStudentSelect`

**Search** (`#searchInput` input event): re-call `GET /api/arquivos/?q=<value>` debounced 300ms.

**Type filter tabs** (`data-filter` click): re-call `GET /api/arquivos/?type=<value>` (omit param for "all").

**Tag pills** (click): re-call `GET /api/arquivos/?tag=<value>`.

**Upload flow:**
1. User clicks `#btnUpload` → `uploadModal.showModal()`
2. On `#uploadForm` submit → `POST /api/arquivos/upload/` as `multipart/form-data`
3. Use `XMLHttpRequest` (not `fetch`) to track upload progress via `xhr.upload.onprogress` → update `#uploadBar`
4. On success: close modal, re-fetch storage info and materials list, reset form

**Link flow:**
1. User clicks `#btnAddLink` → `linkModal.showModal()`
2. On `#linkForm` submit → `POST /api/arquivos/upload/` with `material_type=link`
3. On success: close modal, refresh list

**Edit flow:**
1. User clicks "Editar" on a card → populate `#editForm` fields, set `material_id` and `material_type` hidden inputs, hide `#editUrlRow` if `material_type='file'`, then `editModal.showModal()`
2. On `#editForm` submit → `POST /api/arquivos/<material_id>/`
3. On success: close modal, update card in place (or re-fetch full list)

**Delete flow:**
1. User clicks "Excluir" → set `#deleteMaterialId`, `#deleteModalName`, `deleteModal.showModal()`
2. `#confirmDelete` click → `POST /api/arquivos/<material_id>/delete/`
3. On success: remove card from DOM, re-fetch storage info

**Send to student flow:**
1. User clicks "Enviar para aluno" on a card → set `#sendMaterialId`, default `#sendMaterialDate` to today, `sendModal.showModal()`
2. `#confirmSend` click → `POST /api/arquivos/<material_id>/send-to-student/` with JSON `{ "student_id": ..., "material_date": ..., "title": ... }`
3. On success: show inline toast "Enviado para [nome do aluno]", close modal

**Storage bar rendering:**
```javascript
function renderStorageBar(info) {
  const { used_bytes, used_display, file_count, limits } = info;
  const max = limits.max_total_bytes;
  const pct = max ? Math.min(100, (used_bytes / max) * 100) : 0;
  const maxDisplay = max ? `${max / (1024*1024)} MB` : "Ilimitado";
  document.getElementById("storageUsedLabel").textContent =
    `${used_display} / ${maxDisplay} usados — ${file_count} arquivo(s)`;
  document.getElementById("storageUsedBar").style.width = `${pct}%`;
  document.getElementById("storageUsedBar").style.background =
    pct > 90 ? "var(--overdue)" : pct > 70 ? "var(--todo)" : "var(--primary, #3b82f6)";
}
```

---

## 7. Phase 5 — Dashboard Integration

### 7.1 Sidebar nav link replacement

In both `frontend/templates/index.html` (lines 96–102) and `frontend/templates/dashboard_home.html` (lines 730–736), replace the Tarefas `<a>` block with:

```html
<a href="/arquivos/" class="nav-item">
  <span class="nav-emoji">📁</span>
  <div>
    <p class="nav-title">Arquivos</p>
    <p class="nav-subtitle">Sua biblioteca de materiais</p>
  </div>
</a>
```

The wrapping `{% if not is_partner_teacher %}` block stays in place — Arquivos should also be hidden from partner teachers (they use their own account to store materials).

### 7.2 Dashboard badge

The `tasks_open` badge (removed in Phase 1) can be replaced with an **Arquivos file count** badge as an optional enhancement. This is lower priority; the "Pendencias" section can just show reschedules only.

If the badge is added, the flow is:
- Add `arquivos_count` to the `dashboard_summary_view` response (count of `TeacherMaterial` records for the user)
- Add a badge element near the "Pendencias" `<div>` in `dashboard_home.html`
- Bind it in the JS section (same pattern as the removed `monthTasksOpen` code)

This is optional and can be done in a follow-up PR.

### 7.3 Quick-action button update

In `dashboard_home.html` around line 1466, update the `where === 'tasks'` check to `where === 'arquivos'` (already specified in Phase 1, Section 3.7-E). If there is a button rendered in the dashboard HTML with `data-navigate="tasks"` (search the full file for this attribute), update its value to `data-navigate="arquivos"`.

---

## 8. Phase 6 — "Send to Student" Bridge

### 8.1 Business rules

- **Copy, not reference:** When a teacher sends a `TeacherMaterial` to a student, a new `StudentMaterial` record is created.
  - For **files**: copy the file to `student_materials/%Y/%m/` by reading the original file from storage and re-saving it. Do **not** share the same `FileField` path between a `TeacherMaterial` and a `StudentMaterial`, because deleting one should not affect the other.
  - For **links**: copy the `external_url` string directly — no storage operation needed.
- **No reverse link**: There is intentionally no FK from `StudentMaterial` back to `TeacherMaterial`. The bridge is a one-way copy with no ongoing relationship.
- **Idempotency**: the same `TeacherMaterial` can be sent to the same student multiple times (resulting in multiple `StudentMaterial` records). No de-duplication is enforced.

### 8.2 Full implementation of `send_teacher_material_to_student`

```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_teacher_material_to_student(request, material_id):
    """
    POST /api/arquivos/<material_id>/send-to-student/
    Body JSON: {
      "student_id": int,          (required)
      "title": str,               (optional; overrides original title for the student)
      "material_date": "YYYY-MM-DD"  (optional; defaults to today)
    }
    Returns: { "ok": true, "student_material_id": int }
    """
    from .models import TeacherMaterial, StudentMaterial
    from datetime import date as date_type
    from datetime import datetime
    import io

    # 1. Fetch the TeacherMaterial (must belong to the requesting user)
    try:
        teacher_mat = TeacherMaterial.objects.get(id=material_id, user=request.user)
    except TeacherMaterial.DoesNotExist:
        return Response({"error": "Material não encontrado."}, status=status.HTTP_404_NOT_FOUND)

    # 2. Parse body
    payload = request.data
    student_id = payload.get("student_id")
    if not student_id:
        return Response({"error": "student_id obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

    # 3. Fetch student (must belong to the requesting user's account)
    view = StudentViewSet()
    view.request = request
    view.kwargs = {}
    view.format_kwarg = None
    try:
        student = view.get_queryset_students().get(id=student_id)
    except Student.DoesNotExist:
        return Response({"error": "Aluno não encontrado ou sem permissão."}, status=status.HTTP_404_NOT_FOUND)

    # 4. Resolve title and date
    title = (payload.get("title") or "").strip()[:200] or teacher_mat.title
    raw_date = (payload.get("material_date") or "").strip()
    if raw_date:
        try:
            mat_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Data inválida."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        mat_date = date_type.today()

    # 5. Create StudentMaterial
    if teacher_mat.material_type == TeacherMaterial.TYPE_LINK:
        student_mat = StudentMaterial.objects.create(
            student=student,
            user=request.user,
            title=title,
            material_type=StudentMaterial.TYPE_LINK,
            external_url=teacher_mat.external_url,
            file_size=0,
            material_date=mat_date,
        )
    else:
        # Copy the file bytes into a new StudentMaterial file
        if not teacher_mat.file:
            return Response({"error": "Arquivo original não encontrado."}, status=status.HTTP_400_BAD_REQUEST)
        original_name = os.path.basename(teacher_mat.file.name)
        from django.core.files.base import ContentFile
        try:
            file_bytes = teacher_mat.file.read()
        except Exception:
            return Response({"error": "Não foi possível ler o arquivo original."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        student_mat = StudentMaterial.objects.create(
            student=student,
            user=request.user,
            title=title,
            material_type=StudentMaterial.TYPE_FILE,
            file_size=teacher_mat.file_size,
            material_date=mat_date,
        )
        student_mat.file.save(original_name, ContentFile(file_bytes), save=True)

    return Response({"ok": True, "student_material_id": student_mat.id}, status=status.HTTP_201_CREATED)
```

**Note on `get_queryset_students()`**: The `StudentViewSet` exposes a `get_queryset_students()` helper that respects partner teacher scoping. Follow the same pattern already used in `upload_student_material` (views.py around line 1090–1100) to instantiate the viewset and call this helper.

### 8.3 Field mapping table

| TeacherMaterial field | StudentMaterial field | Notes |
|---|---|---|
| `user` | `user` | Same user (the teacher who sent it) |
| `title` (or request override) | `title` | Override takes priority |
| `material_type` | `material_type` | Direct copy |
| `file` (bytes) | `file` | New file object saved to `student_materials/%Y/%m/` |
| `file_size` | `file_size` | Direct copy |
| `external_url` | `external_url` | Direct copy for links |
| `material_date` from request (or today) | `material_date` | |
| — | `student` | From `student_id` in request body |

---

## 9. Subscription Tier Gating

### 9.1 Is Arquivos gated?

Yes — **all tiers including Basic can use Arquivos**, but storage and file count limits differ. The feature is not blocked behind a paywall; instead, limits enforce differentiation.

Trial users (no subscription) get Basic-tier limits.

### 9.2 Limits per tier

(Defined in `Subscription.get_arquivos_limits()` added in Phase 2)

| Feature | Trial / Basic | Premium | Platinum |
|---|---|---|---|
| Max file size | 10 MB | 20 MB | 50 MB |
| Total storage | 100 MB | 500 MB | 2 GB |
| Max files | 50 | 200 | Unlimited |
| Links | Unlimited | Unlimited | Unlimited |

### 9.3 Upgrade prompt

When any limit is hit, the API returns a 400 with an `error` string that includes the limit and the tier. The frontend should display this error message and, if the user is on Basic or Premium, append a link to `/planos/` with the text "Fazer upgrade".

In `arquivos.html` JS, after receiving a 400 from any upload endpoint, check the response for `error` and display it in a toast or inline alert near the upload button.

---

## 10. Migration and Cleanup Checklist

Execute these steps **in order**. Steps marked [PROD] require a production deployment.

### Step 0 — Prerequisite (do first)
- [ ] Install `django-storages[s3]` and `boto3`, add to `requirements.txt`
- [ ] Set up Cloudflare R2 bucket and credentials
- [ ] Update `config/settings.py` with the `USE_R2_STORAGE` block
- [ ] Set Railway env vars: `USE_R2_STORAGE`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`
- [ ] Migrate existing media files to R2 (use `rclone` or a one-off management command)
- [ ] Test file upload/download in staging with `USE_R2_STORAGE=true` [PROD after passing]

### Step 1 — Remove Tarefas (backend)
- [ ] Delete `Task` class from `core/models.py` (lines 234–276)
- [ ] Delete `TaskSerializer` from `core/serializers.py` (lines 144–163)
- [ ] Remove `Task` from imports in `core/serializers.py` (line 3)
- [ ] Delete `TaskViewSet` from `core/views.py` (lines 433–465)
- [ ] Delete `TasksV2View` from `core/views.py` (lines 1423–1449)
- [ ] Remove `Task` and `TaskSerializer` from imports in `core/views.py` (lines 36–37)
- [ ] Remove `tasks_open` query and dict key from `dashboard_summary_view` in `core/views.py` (lines 5001–5004, 5049)
- [ ] Remove `TaskViewSet` and `TasksV2View` from imports in `core/urls.py` (lines 6, 31)
- [ ] Delete `router.register(r"tasks", ...)` from `core/urls.py` (line 39)
- [ ] Delete both `tarefas-v2/` and `tasks-v2/` URL patterns from `core/urls.py` (lines 49, 74)
- [ ] Remove `Task` from imports in `core/admin.py` (line 2)
- [ ] Delete `TaskAdmin` class from `core/admin.py` (lines 17–21)
- [ ] Run `python manage.py makemigrations core --name="remove_task_model"` → verify only `DeleteModel(Task)`
- [ ] Run `python manage.py migrate` locally and confirm no errors

### Step 2 — Remove Tarefas (frontend)
- [ ] Delete `frontend/templates/tasks_v2.html`
- [ ] Update `frontend/templates/index.html` lines 96–102: replace Tarefas `<a>` with Arquivos `<a>` (see Phase 5 markup)
- [ ] Update `frontend/templates/dashboard_home.html` lines 730–736: replace Tarefas nav link with Arquivos nav link
- [ ] Remove `<span id="monthTasksOpen">` from `dashboard_home.html` (line 1089)
- [ ] Remove `monthTasksOpen` JS binding block from `dashboard_home.html` (lines 1352–1358)
- [ ] Remove `monthTasksOpen` fallback from error handler in `dashboard_home.html` (line 1424)
- [ ] Update `where === 'tasks'` quick-action JS in `dashboard_home.html` (lines 1466–1469) to use `'arquivos'`
- [ ] Search `dashboard_home.html` for `data-navigate="tasks"` — if found, change to `data-navigate="arquivos"`

### Step 3 — Add TeacherMaterial model
- [ ] Add `TeacherMaterial` class to `core/models.py` (after line 684, before `UserProfile`)
- [ ] Add `get_arquivos_limits()` method to `Subscription` model in `core/models.py` (after line 948)
- [ ] Add `TeacherMaterial` to imports in `core/admin.py` and add `TeacherMaterialAdmin` class
- [ ] Run `python manage.py makemigrations core --name="add_teacher_material"` → verify the migration contains `CreateModel(TeacherMaterial)`
- [ ] Run `python manage.py migrate` locally

### Step 4 — Add backend API
- [ ] Add `TeacherMaterial` to model imports in `core/serializers.py` (line 3)
- [ ] Add `TeacherMaterialSerializer` to `core/serializers.py`
- [ ] Add `ARQUIVOS_LIMITS_TRIAL` constant and `TEACHER_MATERIAL_ALLOWED_EXTENSIONS` set to `core/views.py` (top of file, after imports)
- [ ] Add `TeacherMaterial` to model imports in `core/views.py` (line 36)
- [ ] Add `TeacherMaterialSerializer` to serializer imports in `core/views.py` (line 37)
- [ ] Add all Arquivos view functions to `core/views.py` (ArquivosView, `_get_arquivos_limits`, `arquivos_storage_info`, `list_teacher_materials`, `upload_teacher_material`, `delete_teacher_material`, `update_teacher_material`, `send_teacher_material_to_student`)
- [ ] Add URL imports and URL patterns to `core/urls.py` (see Phase 3, Section 5.2)
- [ ] Test all API endpoints with `curl` or DRF browsable API

### Step 5 — Build Arquivos page
- [ ] Create `frontend/templates/arquivos.html` (full spec in Phase 4)
- [ ] Test the page end-to-end: upload, link add, edit, delete, send to student, storage bar

### Step 6 — Deploy to production [PROD]
- [ ] Confirm `USE_R2_STORAGE=true` is set in Railway env
- [ ] Deploy new code
- [ ] Run `python manage.py migrate` on production (removes Task table, adds TeacherMaterial table)
- [ ] Verify `/arquivos/` page loads
- [ ] Verify the sidebar no longer shows "Tarefas"
- [ ] Verify `GET /api/tasks/` returns 404 (route removed)
- [ ] Verify existing student material uploads still work
- [ ] Verify existing lesson plan attachments still work
- [ ] Monitor R2 bucket for new uploads

---

## Appendix A — File locations referenced in this plan

| File | Purpose |
|---|---|
| `core/models.py` | Task (remove), StudentMaterial (reference), TeacherMaterial (add), Subscription.get_arquivos_limits (add) |
| `core/serializers.py` | TaskSerializer (remove), TeacherMaterialSerializer (add) |
| `core/views.py` | TaskViewSet (remove), TasksV2View (remove), dashboard_summary_view tasks_open (remove), all Arquivos views (add) |
| `core/urls.py` | tasks routes (remove), Arquivos routes (add) |
| `core/admin.py` | TaskAdmin (remove), TeacherMaterialAdmin (add) |
| `core/migrations/` | 0054_remove_task_model.py (generate), 0055_add_teacher_material.py (generate) |
| `config/settings.py` | MEDIA_ROOT / storage backend (update for R2) |
| `frontend/templates/tasks_v2.html` | Delete entirely |
| `frontend/templates/arquivos.html` | Create (new) |
| `frontend/templates/index.html` | Sidebar Tarefas → Arquivos link (lines 96–102) |
| `frontend/templates/dashboard_home.html` | Sidebar link (730–736), badge (1089), JS bindings (1352–1358, 1424, 1466–1469) |

## Appendix B — API endpoint summary

| Method | URL | Description |
|---|---|---|
| GET | `/api/arquivos/` | List all teacher materials (filterable) |
| POST | `/api/arquivos/upload/` | Upload file or add link |
| POST | `/api/arquivos/<id>/` | Update title/description/tags/url |
| POST | `/api/arquivos/<id>/delete/` | Delete material and file |
| POST | `/api/arquivos/<id>/send-to-student/` | Copy to StudentMaterial |
| GET | `/api/arquivos/storage-info/` | Current usage and limits |
| GET | `/arquivos/` | Page view (HTML, auth required) |

Removed endpoints (return 404 after deployment):

| Method | URL |
|---|---|
| GET/POST/PATCH/DELETE | `/api/tasks/` and `/api/tasks/<id>/` |
| GET | `/tasks-v2/` |
| GET | `/tarefas-v2/` |
