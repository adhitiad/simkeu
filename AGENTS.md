# AGENTS.md — SIMKEU PTS

Sistem Informasi Keuangan universitas PTS: tagihan, pembayaran, ledger double-entry, anggaran, pengeluaran, pajak, payroll, dan pelaporan. Integrasi eksternal: SIAKAD untuk data akademik dan SIMPEG untuk master pegawai.

## Kondisi repository

- Scaffold Django + uv tersedia dengan modul core, platform_app, billing, payment, ledger, budget, dan academic.
- Branch feat/ledger-core mengimplementasikan fondasi ledger dan trial balance. Dokumen target tata kelola PTS, workflow, pelaporan, dan OpenRouter berada di docs/; dokumen tersebut adalah rancangan, bukan klaim bahwa seluruh modul bisnis sudah berjalan.
- Billing, payment, budget, expenditure, verification, workflow, treasury, reporting, AI assistant, pajak, payroll, audit bisnis, dan sinkronisasi read model akademik masih memerlukan implementasi.
- PostgreSQL lokal diperlukan untuk migrasi dan pengujian integrasi database.

## Aturan kerja

Baca aturan terperinci dalam .agents/rules sebelum mengubah kode:

- 00-core.md: prinsip inti dan Definition of Done.
- 10-architecture.md: modul, event, integrasi, dan health endpoint.
- 15-performance.md: performa, hot path, dan pagination.
- 20-python.md: Python, Django, ORM, transaksi, dan typing.
- 30-database.md: PostgreSQL, schema, constraint, serta migrasi.
- 40-domain-keuangan.md: billing, payment, ledger, pajak, dan periode. Baca juga docs/workflows/pts-financial-workflows.md dan docs/reporting/pts-financial-report-templates.md.
- 50-frontend.md: Django templates, HTMX, dan aksesibilitas.
- 60-security.md: autentikasi, otorisasi, webhook, PII, dan audit.
- 70-testing.md: test dan quality gate.

## Konteks PTS dan tata kelola

- SIMKEU menargetkan PTS yang diselenggarakan badan penyelenggara berbadan hukum nirlaba.
- Bedakan LegalEntity (badan hukum pelapor), Institution (PTS), dan OrganizationUnit (fakultas/biro/unit/cost center). entity_id ledger mengidentifikasi badan hukum, bukan unit anggaran.
- Matriks jabatan, limit, dan sign-off tidak boleh di-hardcode; ikuti Statuta, AD/ART, SOP, dan delegasi tertulis.
- Pisahkan laporan manajemen universitas dari laporan keuangan badan hukum.
- Standar akuntansi dipilih melalui ReportProfile setelah dikonfirmasi pengurus dan akuntan/auditor.

## Stack

Backend: Python 3.14+, Django 6, Django REST Framework, PostgreSQL. Frontend: Django templates + HTMX + Tailwind, tanpa SPA. Batch dan reporting: Celery + RabbitMQ.

## Aturan mutlak

1. Uang menggunakan integer Rupiah. Tidak ada float untuk nilai uang.
2. Ledger append-only dan double-entry. ledger.post adalah satu-satunya jalur tulis. Koreksi menggunakan jurnal pembalik.
3. Pembayaran dan webhook wajib idempotent; deduplikasi berada di payment.inbox.
4. Python strict typing. Hindari Any pada API domain.
5. Error eksplisit dan log terstruktur; tidak boleh silent fail.
6. Perubahan skema hanya melalui Django migrations. Migrasi yang sudah diterapkan tidak diedit.
7. Validasi server selalu wajib.
8. Otorisasi pada service layer, deny-by-default, dan maker-checker untuk aksi finansial sensitif.
9. Secret dan PII tidak boleh masuk repository atau log.
10. Satu schema PostgreSQL per modul; tidak ada query/join lintas schema.
11. Healthz adalah liveness tanpa cek dependency. Readyz melakukan pemeriksaan DB/dependency kritis dan gagal dengan 503.

## Quality gate

    uv sync
    uv run python manage.py check
    uv run python manage.py makemigrations --check --dry-run
    uv run python manage.py migrate
    uv run ruff check . && uv run ruff format --check .
    uv run mypy .
    uv run pytest -q
    uv run bandit -r . -ll
    uv run pip-audit

## Keputusan bisnis yang belum boleh diasumsikan

- Identity provider dan model SSO.
- Object storage untuk bukti pembayaran.
- Provider pembayaran (aggregator atau H2H per bank).
- Kebijakan fail-open/fail-closed untuk gating SIAKAD.
- Struktur COA final dan kebijakan jurnal yang disetujui akuntan/auditor yayasan.
- RBAC dan scope entitas/fakultas/prodi.