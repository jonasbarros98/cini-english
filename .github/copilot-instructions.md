# Copilot / AI agent instructions — Cini English

Purpose: help AI coding agents be immediately productive in this mixed static + Django prototype.

- **Big picture**: this repo is primarily a static dashboard prototype (frontend-first) with an included minimal Django skeleton (`config/`, `core/`, `manage.py`) for future backend work. Front-end behavior and data are located in `index.html` and `script.js`; back-end stubs live in `config/settings.py` and `core/`.

- **Key files**:
  - [README.md](README.md): project intent and how to run the static server (`./start.sh`).
  - [index.html](index.html) and [script.js](script.js): the full UI and client-side state; treat `script.js` as the single source of truth for current app data shapes (students, notes, tasks).
  - [config/settings.py](config/settings.py#L1-L80): Django config — uses SQLite by default and `DEBUG = True`.
  - [manage.py](manage.py#L1-L40): standard Django entrypoint for running local commands.
  - [core/models.py](core/models.py) and [core/views.py](core/views.py): empty stubs for future models/views.

- **Immediate developer workflows**:
  - Static preview (recommended): run `./start.sh` from repository root and open http://localhost:8000. See [README.md](README.md) for notes on clipboard/crypto limitations in local files.
  - Django dev shell / runserver: use `python manage.py runserver` after activating a Python venv. The project uses SQLite at `BASE_DIR / 'db.sqlite3'` by default ([config/settings.py](config/settings.py#L30-L44)).

- **Project-specific conventions & patterns**:
  - Frontend-first: most product logic lives in `script.js`. When adding backend API endpoints, mirror the existing client-side state shape (see `state` object in `script.js` for `students`, `notes`, `tasks`).
  - No current API: there is no REST implementation yet despite `rest_framework` being present in `INSTALLED_APPS` (placeholder). If you implement APIs, prefer route names that match client expectations (e.g., `/api/students/`, `/api/notes/`).
  - Minimal Django usage: the `core` app is empty — add models and serializers cautiously and migrate (`python manage.py makemigrations && python manage.py migrate`) before changing `script.js` to fetch live data.

- **Integration points & external deps**:
  - Client copy-to-clipboard: `script.js` uses `navigator.clipboard.writeText()`; tests running in headless environments may need alternative mocks.
  - `crypto.randomUUID()` is used when available; fallback `uid()` exists in `script.js`.
  - Potential integrations mentioned in README: Supabase/Firebase, Google Calendar, WhatsApp API / Twilio.

- **Testing & debugging notes**:
  - There are no automated tests; `core/tests.py` is empty. For quick verification, use the local static server and browser devtools to exercise UI flows.
  - For Django debugging, run `python manage.py runserver --verbosity 2` and check `db.sqlite3` for persisted data after migrations.

- **What agents should do first (concrete tasks)**:
  1. For frontend changes, update `script.js` and `index.html` only — run `./start.sh` and verify in browser.
  2. For backend work, add models in `core/models.py`, add serializers/views under `core/`, add routes in `config/urls.py`, then run migrations and adapt `script.js` to call the new endpoints.
  3. When adding tests, prefer small integration-style tests exercising the API + a minimal client-side fetch stub.

- **Examples from repo**:
  - Client data shape: see `state.students` and `state.notes` in [script.js](script.js#L1-L40) — use the same `id`, `name`, `plan`, `progress` fields when creating student APIs.
  - Clipboard usage: `copyBilling` handler in [index.html + script.js](script.js#L360-L380) — ensure server changes do not break this synchronous UI flow.

If any section is unclear or you'd like more detail (routes, model examples, or CI/test setup), tell me which part to expand and I will iterate.
