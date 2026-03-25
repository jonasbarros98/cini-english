---
name: project_architecture
description: Stack, key file locations, deployment, and architectural patterns
type: project
---

**Stack:**
- Backend: Django 4.2+ (settings say 6.0 in comments but requirements say >=4.2), Django REST Framework
- Frontend: Vanilla HTML/CSS/JS templates (no React/Vue) served by Django, stored in frontend/templates/
- Database: PostgreSQL (via dj-database-url, psycopg2-binary)
- Auth: Django session auth + Google OAuth (JWT id_token verification via google-auth library)
- Payments: Stripe (stripe Python SDK, webhooks, Checkout Sessions)
- Email: django-anymail[resend] (primary), SMTP Gmail fallback, console backend for dev
- File storage: local disk (/media/), served via Django MEDIA_URL
- Static files: whitenoise (CompressedManifestStaticFilesStorage)
- Deployment: Railway (Procfile: gunicorn config.wsgi:application)

**Key file locations:**
- `config/settings.py` — Django settings (all env vars documented inline)
- `config/urls.py` — Root URL conf (includes core.urls)
- `core/models.py` — ALL models (1246 lines)
- `core/views.py` — ALL views and API logic (7464 lines — monolith)
- `core/urls.py` — All URL patterns (147 lines)
- `core/admin.py` — Django admin registrations
- `core/serializers.py` — DRF serializers
- `core/context_processors.py` — trial_banner context processor
- `core/retention_emails.py` — HTML email templates for retention (trial expiring, canceled)
- `core/management/commands/` — Management commands: create_master_user, send_onboarding_24h_email, send_pending_subscription_recovery_email, send_trial_ending_email, sync_pending_subscriptions
- `frontend/templates/` — All HTML templates (40+ files)
- `railway.json` — Deploy config (preDeployCommand includes migrate + collectstatic + create_master_user)

**Architectural patterns:**
- Single Django app `core` contains all models, views, URLs, serializers
- REST API endpoints under /api/ consumed by JS in templates
- Template-based page views (TemplateView subclasses) do auth check + subscription check in dispatch()
- Permission pattern: _user_has_active_subscription() helper used in all view dispatch methods
- Data isolation: all querysets filtered by request.user (owner) or assigned_teacher (partner)
- Admin flag: UserProfile.is_admin bypasses subscription + data scope checks
- Subscription tiers: Basic (max 15 students, 0 partner teachers), Premium (unlimited students, 2 partners), Platinum (unlimited all)
- Trial: UserProfile.trial_ends_at (7 days from signup); checked in _user_is_in_trial() and _user_has_active_subscription()

**N8N integration:**
- Triggered on signup via threading.Thread (fire-and-forget webhook)
- Internal endpoints for n8n to call back (onboarding_progress_internal, trial_ending_users, mark_trial_email_sent)
- Protected by shared secret: N8N_ONBOARDING_STATUS_TOKEN env var

**STATICFILES_DIRS issue:**
- frontend/templates is listed in STATICFILES_DIRS — this means HTML templates are copied into staticfiles/ on collectstatic. Not ideal but functional.
