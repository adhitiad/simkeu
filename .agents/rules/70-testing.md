---
description: Strategi test dan quality gate untuk Python/Django dan HTMX.
globs: ["**/tests/**", "**/test_*.py", "**/*_test.py", "e2e/**"]
alwaysApply: false
---
# 70 — Testing dan Quality Gate

## Prinsip

- Test ditulis bersama kode. Bug fix dimulai dari test yang gagal.
- Test deterministik: tidak bergantung waktu nyata, urutan, atau jaringan. Waktu dan UUID diinjeksi.
- Jangan melemahkan assertion, menghapus test, atau menambah skip agar build lolos.

## Python/Django

- `pytest` + `pytest-django`. Test repository dan alur transaksi terhadap **PostgreSQL nyata** (container ephemeral), bukan mock ORM. Skema dibangun dengan Django migrations yang sama dengan production.
- **Property-based test** (Hypothesis) untuk invarian: jurnal selalu seimbang, total alokasi = nominal pembayaran, pembulatan proration tidak membuat nominal hilang/bertambah.
- **Test konkurensi**: pembayaran dengan `provider_ref` sama dikirim paralel → efek ledger tepat satu. Dua alokasi bersamaan ke akun yang sama → saldo konsisten, tanpa deadlock.
- **Fuzz test** untuk parser webhook dan input eksternal (Hypothesis).
- **Golden test** untuk laporan keuangan (neraca, penghasilan komprehensif, arus kas).
- Test migrasi: `migrate` → `migrate <app> <prev>` → `migrate` bersih. Test trigger: ledger menolak `UPDATE/DELETE`, periode tertutup menolak posting.
- Test health endpoint: `/healthz` selalu 200 selama proses hidup meski DB mati (tanpa cek dependency); `/readyz` 503 saat DB/dependency kritis tidak terjangkau.

## Frontend (HTMX)

- Template partial diuji dengan test view/Django test client (status, konten fragment, HTMX headers).
- Skema/validasi diuji dengan fixture valid dan invalid, termasuk uang non-integer, UUID salah, dan enum tak dikenal.
- E2E (Playwright) untuk alur kritis: lihat tagihan → bayar (VA/QRIS sandbox) → status berubah; approval maker-checker; tutup periode.
- Tidak ada `Any` di file test.

## Domain (wajib ada kasus)

- Pembayaran: parsial, lebih bayar, kurang bayar, duplikat, out-of-order, reversal, ke tagihan void.
- Tagihan: perubahan tarif retroaktif, pindah prodi, cuti, revisi KRS, lulus di tengah semester.
- Periode: posting ke periode tertutup, jurnal pembalik, batas pergantian periode (WIB vs UTC).
- Otorisasi: akses lintas scope ditolak, maker = checker ditolak.

## CI gate (semua harus hijau)

`python manage.py check`, `makemigrations --check --dry-run`, `migrate`, `ruff check`, `ruff format --check`, `mypy --strict`, `pytest`, `bandit`, `pip-audit`, migrasi up/down, build CSS, serta **ZAP Baseline Scan** terhadap staging (lihat `60-security.md`).