# SIMKEU PTS

Sistem Informasi Keuangan Perguruan Tinggi Swasta — tagihan, pembayaran, ledger double-entry, anggaran, pengeluaran, pajak, payroll, pelaporan. Terintegrasi dengan SIAKAD Sister dan SIMPEG.

Stack: Python 3.14.5 + Django 6 + DRF + HTMX + Tailwind + PostgreSQL + Celery/RabbitMQ.

## Virtual environment

Dependency dikelola `uv` di `.venv/` (project root). Direktori ini **tidak di-commit** (sudah masuk `.gitignore`) dan bisa dibuat ulang kapan saja dari `pyproject.toml` + `uv.lock`:

```bash
uv sync
```

Semua perintah disarankan lewat `uv run` agar otomatis memakai interpreter `.venv/`. Tidak perlu jalankan `python -m venv` atau `pip install` manual.

Jika muncul warning `VIRTUAL_ENV=.venv314 does not match the project environment path .venv`, itu variabel lama di terminal/VS Code. Tutup terminal lalu buka lagi, atau jalankan:

```powershell
Remove-Item Env:VIRTUAL_ENV
```

Di VS Code, pilih interpreter `.venv\Scripts\python.exe` (sudah di-set di `.vscode/settings.json`).

## Setup

```bash
uv sync
cp .env/.env.example .env/.env.local
# isi SECRET_KEY dan DATABASE_URL di .env/.env.local
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

PostgreSQL + RabbitMQ cepat via Docker:

```bash
docker compose up -d
```

Environment: file konfigurasi ada di `.env/**`. Default membaca `.env/.env` lalu overlay `.env/.env.local`. Untuk staging/production:

```bash
APP_ENV=staging uv run python manage.py check
APP_ENV=production ENV_FILE=/path/rahasia/.env uv run python manage.py check
```

## Gate

```bash
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run ruff check .
uv run mypy .
uv run pytest -q
uv run bandit -r . -ll
uv run pip-audit
```

## Struktur

- `simkeu/` — project Django (settings, urls, celery, wsgi/asgi)
- `apps/core` — halaman dasar + health endpoint
- `apps/platform_app` (label `platform`) — outbox, audit, auth
- `apps/billing`, `apps/payment`, `apps/ledger`, `apps/budget`
- `apps/academic` — anti-corruption layer SIAKAD Sister & SIMPEG
- `templates/` — base template + partial HTMX

Endpoint: `/healthz`, `/readyz`, `/metrics`, `/api/docs`.
