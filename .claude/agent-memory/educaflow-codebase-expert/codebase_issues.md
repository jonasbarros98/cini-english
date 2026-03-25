---
name: codebase_issues
description: Known issues, technical debt, and gaps identified in the codebase
type: project
---

**Critical / Production risks:**

1. `DEBUG = True` hardcoded in config/settings.py (line 32). Never reads from env var. Must be fixed before trusting the production deployment as hardened.

2. `STATICFILES_DIRS` includes `frontend/templates` (the HTML templates directory). This causes all HTML templates to be copied into staticfiles/ on collectstatic. While it works, it exposes template source files as static assets and can cause collectstatic failures if template filenames collide with other static asset names.

3. No test suite — `core/tests.py` is empty (3 lines). There is zero automated test coverage.

4. 132 `print()` / `[DEBUG]` statements scattered throughout `core/views.py` (7464 lines). These print to production logs including sensitive info (profile data, serializer payloads). Should be replaced with proper `logging` calls.

5. `core/views.py` is a 7464-line monolith. All view logic, business logic, Stripe webhook handling, auth, admin panel, n8n integration, and email sending live in one file. No separation of concerns.

**Missing from Django admin:**
- StudentHomework, StudentHomeworkMessage, StudentMaterial, StudentShareToken, RetentionEmailLog are NOT registered in admin.py. Makes debugging/support harder.

**Minor issues:**
- `threading.Thread` used for n8n webhook (fire-and-forget). On Railway with single worker/process this works, but it's fragile — no retry, no persistence if the process dies mid-flight.
- `ALLOWED_HOSTS = ["*"]` — acceptable behind Railway's proxy but not ideal.
- `CSRF_COOKIE_SECURE` reads from env but `DEBUG` does not — inconsistency.
- `google-auth` version pinned to `>=2.29.0` without upper bound — could break on major version bump.
- The `DayNote.__str__` method has unreachable code after `return` (lines 975-980 in models.py — `verbose_name_plural` and `is_active` property appear to be accidentally placed inside `DayNote` class due to copy-paste from `Subscription`). This is a models.py structural bug.
- `ssl_require=True` is commented out in the database config. Production DB connection has no SSL enforcement from Django side (Railway handles SSL at network level, so functionally OK but worth noting).
