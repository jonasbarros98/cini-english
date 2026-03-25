# R2 Storage Debug Report

**File:** `config/settings.py`, `requirements.txt`, `config/urls.py`
**Date:** 2026-03-25
**Symptom:** Files are uploading to the local filesystem instead of Cloudflare R2. The R2 bucket remains empty.

---

## 1. Current settings.py R2 Block (as-is, lines 216–264)

```python
# Media files (uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Persistência de uploads no Railway (PRD):
# - Postgres persiste apenas metadados (caminho/nome do arquivo), não os bytes.
# - Em produção (Railway), o disco local pode ser efêmero.
# - Portanto, quando `USE_R2_STORAGE=true`, usamos storage compatível com S3 (Cloudflare R2)
#   via `django-storages` para que os bytes persistam fora do container.
USE_R2_STORAGE = os.environ.get("USE_R2_STORAGE", "").lower() in ("1", "true", "yes")

if USE_R2_STORAGE:
    # Cloudflare R2 usa credenciais S3 + endpoint customizado.
    # No Railway, configure as variáveis: R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME e R2_ENDPOINT_URL.
    AWS_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
    AWS_S3_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "")

    # Alguns setups exigem uma região "fake" (não é usada pelo R2).
    AWS_S3_REGION_NAME = os.environ.get("R2_REGION_NAME", "auto")

    # Cloudflare R2 costuma funcionar melhor com addressing estilo "path".
    AWS_S3_ADDRESSING_STYLE = os.environ.get("R2_S3_ADDRESSING_STYLE", "path")
    AWS_S3_SIGNATURE_VERSION = os.environ.get("R2_S3_SIGNATURE_VERSION", "s3v4")

    # Endereço/URL gerados pelo storage: por padrão usamos URL assinada.
    AWS_QUERYSTRING_AUTH = True
    AWS_DEFAULT_ACL = None

    # Garante que o cache/etag faça sentido em downloads.
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": os.environ.get("R2_CACHE_CONTROL", "max-age=86400"),
    }

    # Apenas mídia (FileField) no R2. Não definir STORAGES["staticfiles"] aqui: misturar
    # S3 default + Whitenoise via STORAGES pode quebrar staticfiles no Django 6 e gerar 500.
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

    # Diagnóstico no Railway: confirmar que o backend de storage R2/S3 está ativo.
    # (Não imprime secrets; ajuda a verificar "por que o bucket ficou vazio".)
    print(
        "[R2] ENABLED",
        f"bucket={AWS_STORAGE_BUCKET_NAME}",
        f"endpoint={AWS_S3_ENDPOINT_URL}",
        f"addressing={AWS_S3_ADDRESSING_STYLE}",
        f"access_key_set={bool(AWS_ACCESS_KEY_ID)}",
        f"secret_key_set={bool(AWS_SECRET_ACCESS_KEY)}",
    )
```

---

## 2. Root Cause Analysis

Issues are ranked from most to least likely to be the actual reason files are not reaching R2.

### Issue 1 — CRITICAL: `R2_ACCESS_KEY_ID` is likely missing from Railway (highest likelihood)

The `print` statement at startup will show `access_key_set=False` in Railway logs if this variable is not set. When `AWS_ACCESS_KEY_ID` is an empty string, boto3 will either raise an `NoCredentialsError` at upload time or silently fall through depending on its credential chain resolution. Either way, no file reaches R2.

The context confirms this variable "possibly missing — not confirmed yet." This is the single most likely cause. Everything else in the settings block is structurally correct.

**What to check:** In Railway logs, find the startup line beginning with `[R2] ENABLED`. If it shows `access_key_set=False`, this is your root cause. Stop here and add the variable.

---

### Issue 2 — LIKELY: `USE_R2_STORAGE` env var value does not match the accepted set

Line 225:
```python
USE_R2_STORAGE = os.environ.get("USE_R2_STORAGE", "").lower() in ("1", "true", "yes")
```

The code accepts only the lowercase strings `"1"`, `"true"`, or `"yes"`. The Railway dashboard shows the value as `True` (capital T). When Railway stores environment variable values, it stores them as strings. The string `"True"` (capital T) — after `.lower()` — becomes `"true"`, which IS in the accepted set. So `"True"` works fine.

However, if the value was accidentally set to `"true "` (trailing space), `"TRUE"` (after `.lower()` becomes `"true"` — fine), or `"yes "` (trailing space), it would not match. Trailing spaces are invisible in the Railway dashboard UI.

**What to check:** In Railway, view the raw value. If there is any whitespace around it, remove it.

---

### Issue 3 — LIKELY: `R2_ENDPOINT_URL` format is wrong

boto3 / s3boto3 is strict about the endpoint URL format. Cloudflare R2 endpoint URLs look like:

```
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

Common mistakes:
- Trailing slash: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com/` — boto3 may double-slash paths.
- Missing `https://` scheme — boto3 will reject it or try HTTP.
- Including the bucket name in the URL: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com/<BUCKET>` — this is wrong because `AWS_S3_ADDRESSING_STYLE = "path"` already appends the bucket name to the path.

**What to check:** The value of `R2_ENDPOINT_URL` in Railway should be exactly `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` — no trailing slash, no bucket name appended.

---

### Issue 4 — MODERATE: `DEFAULT_FILE_STORAGE` is a Django 3.x/4.x setting; Django 4.2+ prefers `STORAGES`

Line 253:
```python
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
```

The comment in the file itself says the `STORAGES` dict "broke things and was reverted," and the current code uses the legacy `DEFAULT_FILE_STORAGE` key instead.

In Django 4.2, `DEFAULT_FILE_STORAGE` was deprecated in favour of the `STORAGES` dict. The `requirements.txt` file specifies `Django>=4.2` (without an upper bound), so the installed version on Railway could be Django 4.2, 5.x, or 6.x.

Critically, Django 4.2 still honours `DEFAULT_FILE_STORAGE` and emits only a deprecation warning — it does not break. However, **Django 5.0 removed `DEFAULT_FILE_STORAGE` entirely**. If Railway is running Django 5.x or 6.x (which this project targets based on the settings file comment "Django 6.0"), then `DEFAULT_FILE_STORAGE` is silently ignored, and Django falls back to its own default (`FileSystemStorage`). This would explain exactly the symptom: no error, but files go to the local disk.

Check the installed Django version in Railway logs or by running `python -m django --version` in a Railway shell. If it is 5.0 or above, `DEFAULT_FILE_STORAGE` does nothing and must be replaced with the `STORAGES` dict.

**This may be the actual root cause if Django >= 5.0 is installed.**

---

### Issue 5 — LOW: `AWS_QUERYSTRING_AUTH = True` with a private bucket and no public domain configured

Line 243:
```python
AWS_QUERYSTRING_AUTH = True
```

This means every URL generated for a media file will be a pre-signed URL with an expiry. This is functionally correct for private buckets, but it means:
- Uploaded files appear in the bucket (upload works) but URLs expire after a time.
- If you are checking "is the file visible at `/media/...`" in the browser and it returns 403, this is not an upload failure — the file IS in R2, the pre-signed URL expired or was not generated properly.

This is not a reason files fail to upload, but it is worth knowing when verifying that R2 is working.

---

### Issue 6 — LOW: `MEDIA_URL = "/media/"` is still set and local media directory still exists

Lines 217–218:
```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

These two lines are always set, regardless of `USE_R2_STORAGE`. When the R2 backend is active, `MEDIA_URL` and `MEDIA_ROOT` are ignored by `S3Boto3Storage` for file storage, so they cause no conflict. However, if any view or template constructs a media URL manually using `settings.MEDIA_URL` instead of calling `file_field.url`, it will produce a local path that does not exist in R2. This is a secondary issue to investigate only after uploads are confirmed to be reaching R2.

---

### Issue 7 — LOW: `urls.py` local media serving is gated on `DEBUG` (correct)

`config/urls.py` line 12:
```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

`DEBUG = False` is hardcoded in `settings.py` line 32. This means local media serving is never active in Railway. This is correct behaviour and is not causing the problem. It does mean that if the R2 storage is broken, file URLs will return 404 in production (no fallback local serving), which helps confirm something is wrong.

---

## 3. Step-by-Step Fix Instructions

Apply these fixes in order. Fix 1 and Fix 2 are environment variable changes in Railway (no code edits). Fix 3 is a code change required only if Django >= 5.0 is installed.

---

### Fix 1 — Add `R2_ACCESS_KEY_ID` to Railway (environment variable, no code change)

1. Open the Cloudflare dashboard.
2. Go to **R2 Object Storage** > **Manage R2 API Tokens**.
3. Create a new API token (or use an existing one) with **Object Read & Write** permission scoped to your bucket.
4. Copy the **Access Key ID** value (it looks like a 32-character alphanumeric string).
5. In Railway: open your service > **Variables** tab > add:
   - Name: `R2_ACCESS_KEY_ID`
   - Value: the Access Key ID you copied

After adding this variable, redeploy. In Railway logs, look for:
```
[R2] ENABLED bucket=<your-bucket> endpoint=<your-endpoint> addressing=path access_key_set=True secret_key_set=True
```
Both `access_key_set` and `secret_key_set` must be `True`.

---

### Fix 2 — Verify `R2_ENDPOINT_URL` has no trailing slash (environment variable check)

In Railway, find `R2_ENDPOINT_URL` and confirm its value is exactly:
```
https://<YOUR_ACCOUNT_ID>.r2.cloudflarestorage.com
```
No trailing slash. No bucket name appended. Replace `<YOUR_ACCOUNT_ID>` with the 32-character hex ID from the Cloudflare dashboard URL (visible in the R2 section URL bar as `dash.cloudflare.com/<ACCOUNT_ID>/r2`).

If there is a trailing slash, remove it and redeploy.

---

### Fix 3 — Replace `DEFAULT_FILE_STORAGE` with the `STORAGES` dict (code change, required if Django >= 5.0)

First, determine the installed Django version. In a Railway shell or deploy log, run:
```
python -m django --version
```

If the version is **5.0 or higher**, `DEFAULT_FILE_STORAGE` is completely ignored. You must replace it with the `STORAGES` dict.

**File:** `config/settings.py`
**Approximate lines:** 251–253

Current code (the line to replace inside the `if USE_R2_STORAGE:` block):
```python
    # Apenas mídia (FileField) no R2. Não definir STORAGES["staticfiles"] aqui: misturar
    # S3 default + Whitenoise via Storages pode quebrar staticfiles no Django 6 e gerar 500.
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
```

Replace with:
```python
    # Apenas mídia (FileField) no R2. O STORAGES["staticfiles"] permanece com Whitenoise
    # (não definido aqui) para evitar conflito com CompressedManifestStaticFilesStorage.
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": STATICFILES_STORAGE,
        },
    }
```

Important note on this replacement: `STATICFILES_STORAGE` is set earlier in the file (lines 211–214) to either `"django.contrib.staticfiles.storage.StaticFilesStorage"` or `"whitenoise.storage.CompressedManifestStaticFilesStorage"` depending on the `DJANGO_STATICFILES_SIMPLE` env var. Referencing it directly in the `STORAGES` dict preserves that existing logic and avoids breaking static file serving. This is precisely what "broke things" before if the previous attempt hard-coded the staticfiles backend instead.

If Django version is **4.2.x**, `DEFAULT_FILE_STORAGE` still works (with a deprecation warning) and this code change is optional but recommended to future-proof the project before Django drops the setting entirely.

---

## 4. Railway Environment Variables Checklist

All four of these must be set in Railway for R2 to work. Verify each one:

| Variable | Required | Where to get the value |
|---|---|---|
| `USE_R2_STORAGE` | Yes | Set to `true` (no quotes, no spaces) |
| `R2_ACCESS_KEY_ID` | Yes | Cloudflare dashboard > R2 > Manage R2 API Tokens > your token's **Access Key ID** |
| `R2_SECRET_ACCESS_KEY` | Yes | Cloudflare dashboard > R2 > Manage R2 API Tokens > your token's **Secret Access Key** (shown only once at creation time) |
| `R2_BUCKET_NAME` | Yes | Cloudflare dashboard > R2 > the exact bucket name (case-sensitive, e.g. `educaflow-media`) |
| `R2_ENDPOINT_URL` | Yes | Cloudflare dashboard > R2 > your bucket > **Settings** tab > **S3 API** section. Copy the endpoint, it looks like `https://<account_id>.r2.cloudflarestorage.com`. Do not include the bucket name. |

Optional variables (have working defaults in the code):

| Variable | Default | When to override |
|---|---|---|
| `R2_REGION_NAME` | `auto` | Leave as default for R2 |
| `R2_S3_ADDRESSING_STYLE` | `path` | Leave as default for R2 |
| `R2_S3_SIGNATURE_VERSION` | `s3v4` | Leave as default for R2 |
| `R2_CACHE_CONTROL` | `max-age=86400` | Override if you want different browser caching for uploaded files |

---

## 5. How to Verify It Is Working After Deploy

### Step 1 — Check the startup log line

Immediately after deploy, search Railway logs for:
```
[R2] ENABLED
```

Expected output:
```
[R2] ENABLED bucket=educaflow-media endpoint=https://<account_id>.r2.cloudflarestorage.com addressing=path access_key_set=True secret_key_set=True
```

If `access_key_set=False` or `secret_key_set=False`, stop — the credentials are missing. Fix them in Railway variables and redeploy.

If this line does not appear at all, `USE_R2_STORAGE` evaluated to `False`. Check the variable value in Railway for trailing spaces or unexpected capitalisation.

### Step 2 — Trigger a file upload through the app

Log into the production app and upload any file (e.g. a student profile photo or a lesson material attachment — whatever uses a `FileField` or `ImageField` in the app). Watch the Railway log for any error immediately after the upload request. A successful upload to R2 produces no error. A failed upload will produce an `Exception` with a boto3 or botocore traceback (e.g. `NoCredentialsError`, `EndpointResolutionError`, `ClientError: Access Denied`).

### Step 3 — Confirm the file appears in the Cloudflare R2 bucket

1. Open Cloudflare dashboard > R2 > your bucket.
2. Click **Browse** (or the Objects tab).
3. You should see the uploaded file. The path will typically be the value stored in the Django model's `FileField` (e.g. `lesson_materials/filename.pdf`).

If the file appears here, R2 is receiving uploads correctly.

### Step 4 — Confirm the file URL resolves (optional, for pre-signed URL behaviour)

With `AWS_QUERYSTRING_AUTH = True`, the URL returned by `instance.file_field.url` will be a pre-signed S3-compatible URL that expires. To test:
1. In a Django shell on Railway (`railway run python manage.py shell`) or via a debug view, print `instance.file_field.url`.
2. Paste the URL into a browser. It should return the file (HTTP 200) within the expiry window.

If it returns HTTP 403 and the file is visible in the bucket, the pre-signed URL mechanism is working but something in the app is caching or reusing an expired URL — that is a separate issue from the upload itself.

### Step 5 — Confirm nothing is written to the local media directory

In a Railway shell:
```
ls media/
```
After uploads with R2 active, this directory should remain empty (or not exist). If new files keep appearing here, `DEFAULT_FILE_STORAGE` is still being ignored (Django >= 5.0 issue) and Fix 3 above must be applied.
