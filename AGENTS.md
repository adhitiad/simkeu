# AGENTS.md — SIMKEU PTS

Sistem Informasi Keuangan universitas PTS: tagihan, pembayaran, ledger double-entry, anggaran, pengeluaran, pajak, payroll, pelaporan. Integrasi eksternal: SIAKAD (gating akademik) dan SIMPEG (master pegawai).

## Kondisi repo saat ini (penting)

- Scaffold Django + uv sudah ada: `manage.py`, `pyproject.toml`, `uv.lock`, `simkeu/`, `apps/` (core, platform_app, billing, payment, ledger, budget, academic), `templates/`, `tests/`.
- Modul bisnis masih kerangka (model/service/domain belum lengkap). Cek dulu sebelum merujuk implementasi yang belum ada.
- Gate di bagian Commands sudah bisa dijalankan dengan `uv run`; PostgreSQL lokal dan role `simkeu` diperlukan untuk `migrate`/`pytest`.

## Aturan terperinci di `.agents/rules/`

Jika tool agent tidak memuat rules otomatis, **baca file yang relevan sebelum menulis kode**. Konflik antar rules: nomor file lebih kecil menang. Konflik dengan instruksi eksplisit pengguna: tanyakan, jangan asumsikan.

| Mengerjakan | Wajib baca |
|---|---|
| Apa pun | `00-core.md` |
| Struktur modul, event, integrasi, health endpoint | `10-architecture.md` |
| Performa, hot path, budget, caching | `15-performance.md` |
| Kode Python, Django, ORM | `20-python.md` |
| Skema, migrasi Django, query | `30-database.md` |
| Tagihan, pembayaran, ledger, pajak, istilah domain | `40-domain-keuangan.md` |
| Django templates, HTMX, Tailwind, aksesibilitas | `50-frontend.md` |
| Auth, webhook, PII, secret, upload | `60-security.md` |
| Test dan quality gate | `70-testing.md` |

## Stack (target)

Backend: Python 3.12+, Django, Django REST Framework (BFF/API), PostgreSQL. Frontend: Django templates + HTMX + Tailwind CSS (server-rendered; tanpa SPA). Batch/reporting/rekonsiliasi: Python (Celery + RabbitMQ). Bahasa: Python (strict type hints), SQL, HTML/HTMX.

## Aturan mutlak

1. Uang = integer Rupiah (`int` di Python, divalidasi `int` tanpa desimal). Tidak ada float.
2. Ledger append-only, double-entry; `ledger.post(...)` satu-satunya jalur tulis. Koreksi hanya lewat jurnal pembalik.
3. Endpoint pembayaran dan webhook wajib idempotent; dedupe via `payment.inbox` (`UNIQUE (provider, provider_ref)`).
4. Python: tanpa `Any` di API domain; semua fungsi bertipe; lolos `mypy --strict` (atau pyright strict). Template/JS: tanpa `any` implisit.
5. Error eksplisit + log terstruktur. Tidak ada silent fail, `_ = err`/`except: pass`, atau `sys.exit` di request path.
6. Skema DB berubah hanya lewat Django migrations. Tanpa `makemigrations --runsyncdb` di production atau edit skema manual. Migrasi yang terlanjur diterapkan tidak diubah; perbaikan = migrasi baru.
7. Validasi server (Django/Python) selalu ada. Validasi client (HTMX/JS) bukan batas keamanan.
8. Otorisasi di service layer, deny-by-default, maker-checker untuk aksi finansial sensitif.
9. Tidak ada secret atau PII di repo maupun log.
10. Satu schema PostgreSQL per modul; dilarang query/join lintas schema modul.
11. Keamanan mengacu OWASP Top 10:2025; DAST via ZAP di CI melawan staging saja — tidak pernah production (lihat `60-security.md`).
12. `/healthz` (liveness) tanpa cek dependency; `/readyz` (readiness) cek DB + dependency kritis dengan timeout pendek, gagal = 503 (lihat `10-architecture.md`).
13. Selesai = lolos semua gate di bawah.

## Commands (gate wajib; berlaku setelah kode & tooling ada)

```bash
# Python (uv; venv dikelola uv)
uv sync
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest -q
uv run bandit -r . -ll
uv run pip-audit

# Migrasi (Django): up lalu down (rollback) lalu up untuk verifikasi
uv run python manage.py migrate <app> <prev>
uv run python manage.py migrate <app>

# Frontend (HTMX/Tailwind): build CSS via django-tailwind
uv run python manage.py tailwind build

# DAST (CI, bukan lokal): ZAP Baseline terhadap staging tiap rilis;
# ZAP Full Scan terjadwal mingguan. High = fail build. Lihat 60-security.md
```

## Cara kerja agent

1. Baca rules yang relevan, lalu kode sekitar. Ikuti konvensi yang sudah ada.
2. Perubahan yang menyentuh ledger, pembayaran, migrasi, otorisasi, atau lebih dari satu modul: tulis rencana singkat dulu.
3. Implementasi kecil dan terisolasi. Tanpa refactor di luar scope. Tanpa dependency baru tanpa alasan tertulis.
4. Tulis test bersama kodenya. Jangan melemahkan test/lint/tipe agar build lolos.
5. Ringkasan akhir: Perubahan · Trade-off (bullet) · Risiko/asumsi · Cara verifikasi. Tanpa preamble, tanpa permintaan maaf.

Bahasa: respons ke pengguna dalam Bahasa Indonesia. Identifier, tabel, endpoint: English. Teks UI pengguna akhir: Bahasa Indonesia. Domain glossary: `40-domain-keuangan.md`.

## Keputusan terbuka (jangan diasumsikan; ajukan opsi dan trade-off)

- Tooling frontend (npm/pnpm) — package manager Python sudah diputuskan: uv
- IdP / mekanisme autentikasi (Django auth vs SSO)
- Task queue sudah diputuskan: Celery + RabbitMQ; Redis tidak dipakai
- Object storage untuk bukti bayar
- Payment provider: aggregator vs H2H per bank
- Test runner frontend/e2e (pytest + Playwright)
- Kebijakan fail-open/fail-closed gating SIAKAD saat layanan tidak terjangkau (keputusan bisnis)
- Tailwind build pipeline (npm vs django-tailwind)