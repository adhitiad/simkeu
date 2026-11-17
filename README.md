# SIMKEU PTS

Sistem Informasi Keuangan Perguruan Tinggi Swasta: tagihan, pembayaran, ledger double-entry, anggaran, pengeluaran, pajak, payroll, dan pelaporan. Terintegrasi dengan SIAKAD Sister dan SIMPEG.

Stack: Python 3.14.5, Django 6, Django REST Framework, HTMX, Tailwind, PostgreSQL, Celery, dan RabbitMQ.

## Status implementasi

### Fondasi ledger tersedia pada branch feat/ledger-core

- Bagan akun per entitas: tipe akun, saldo normal, akun induk, dan status aktif.
- Periode akuntansi dengan pemeriksaan tumpang tindih di model dan database, serta penutupan maker-checker.
- Posting jurnal double-entry dalam satu transaksi database.
- Idempotensi berdasarkan entity_id + source_type + source_id. Retry dengan payload yang sama mengembalikan jurnal lama; payload berbeda ditolak.
- Validasi akun aktif dan kepemilikan entitas; tanggal bisnis harus berada di periode terbuka.
- Proteksi PostgreSQL untuk jurnal append-only; akun yang sudah dipakai tidak bisa mengubah klasifikasi; periode tidak dapat digeser setelah memiliki jurnal, ditutup permanen, dan tidak boleh tumpang tindih.
- API jurnal dengan autentikasi admin/staff dan keyset cursor pagination.
- Trial balance per tanggal untuk semua akun, termasuk akun tanpa mutasi; memuat total mutasi dan saldo akhir debit/kredit.

Endpoint:
- GET /api/ledger/journals?entity_id=10&limit=50
- GET /api/ledger/journals?entity_id=10&limit=50&cursor=<next_cursor>
- POST /api/ledger/journals
- GET /api/ledger/reports/trial-balance?entity_id=10&as_of=2026-11-17

Payload POST membutuhkan entity_id, business_date, source_type, source_id, description, dan minimal dua baris lines. Setiap baris memiliki account_id UUID, debit integer Rupiah, credit integer Rupiah, dan description opsional.

Trial balance menghitung seluruh jurnal posted sampai tanggal as_of. Saldo awal wajib direpresentasikan sebagai jurnal pembukaan; laporan tidak mengarang saldo dari data di luar ledger.

API saat ini dibatasi untuk pengguna Django is_staff. RBAC berbasis entitas/fakultas/prodi perlu diselesaikan sebelum akses diberikan kepada operator unit.

### Belum diimplementasikan

- Billing/tagihan mahasiswa, tarif berversi, beasiswa, dispensasi, cicilan, dan denda.
- Penerimaan pembayaran VA/QRIS, webhook provider, inbox idempotent, alokasi multi-tagihan, refund, dan rekonsiliasi bank.
- Anggaran/RAPB, pengajuan dana, komitmen, SPJ, dan approval berjenjang.
- Pajak, payroll, laporan neraca/penghasilan komprehensif/arus kas, dan ekspor Coretax.
- Integrasi produksi SIAKAD Sister dan SIMPEG.

Bagian tersebut membutuhkan kontrak provider, kebijakan akuntansi yayasan, struktur COA yang disetujui, dan aturan otorisasi bisnis; tidak boleh diisi dengan asumsi teknis semata.

## Virtual environment

Dependency dikelola uv di direktori .venv pada root project. Direktori ini tidak di-commit dan dapat dibuat ulang dari pyproject.toml serta uv.lock:

    uv sync

Gunakan uv run agar perintah memakai interpreter project. Di VS Code, pilih .venv\\Scripts\\python.exe.

## Setup

    uv sync
    cp .env/.env.example .env/.env.local
    # isi SECRET_KEY dan DATABASE_URL di .env/.env.local
    uv run python manage.py migrate
    uv run python manage.py createsuperuser
    uv run python manage.py runserver

PostgreSQL dan RabbitMQ untuk pengembangan dapat dijalankan dengan:

    docker compose up -d

Default konfigurasi membaca .env/.env, lalu overlay .env/.env.local. Untuk staging/production gunakan APP_ENV dan ENV_FILE serta kredensial dari secret manager.

## Quality gate

    uv run python manage.py check
    uv run python manage.py makemigrations --check --dry-run
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy .
    uv run pytest -q
    uv run bandit -r . -ll
    uv run pip-audit

## Struktur

- simkeu/: konfigurasi Django, URL, Celery, WSGI/ASGI.
- apps/core: beranda dan health endpoint.
- apps/platform_app: outbox dan audit platform.
- apps/ledger: bagan akun, periode, jurnal double-entry, trial balance, API ledger.
- apps/billing, apps/payment, apps/budget: modul lanjutan.
- apps/academic: anti-corruption layer SIAKAD Sister dan SIMPEG.
- templates/: template server-rendered.

Endpoint operasional: /healthz, /readyz, /metrics, /api/docs.

## Arsitektur dan tata kelola PTS

Dokumen rancangan:
- docs/architecture/pts-governance-and-operating-model.md
- docs/workflows/pts-financial-workflows.md
- docs/reporting/pts-financial-report-templates.md
- docs/ai/openrouter-financial-assistant.md

Pemisahan penting: entity_id ledger adalah badan hukum pelapor; universitas, fakultas, biro, program studi, dan unit menjadi dimensi organisasi/cost center. Persetujuan final mengikuti Statuta, AD/ART, SOP keuangan, dan delegasi tertulis.
