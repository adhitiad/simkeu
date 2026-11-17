---
description: Performa — ukur dulu, hot path, budget, pagination, caching, frontend HTMX.
globs: ["services/**", "apps/**", "db/**"]
alwaysApply: false
---
# 15 — Performance

## Prinsip

- Ukur sebelum mengoptimasi: `py-spy`, `pytest-benchmark`, `EXPLAIN (ANALYZE, BUFFERS)`. Klaim performa wajib disertai angka sebelum/sesudah.
- Tentukan budget per endpoint/job (mis. p95) dan pantau lewat metrik RED; tanpa budget, "cepat" tidak bisa diperdebatkan.
- Optimasi hanya di jalur yang terbukti panas. Jangan mengoptimasi kode yang tidak diukur.

## Hot path (prioritas)

- Bulk billing, webhook, alokasi pembayaran, posting ledger, rekonsiliasi.
- N+1 dilarang (lihat `20-python.md`, `30-database.md`). Query ledger/alokasi/laporan berat: SQL eksplisit, bukan ORM berlapis.
- Panggilan eksternal (SIAKAD, SIMPEG, provider pembayaran): timeout eksplisit, retry hanya idempotent, circuit breaker (lihat `10-architecture.md`).

## Data besar

- Keyset pagination, bukan `OFFSET` besar. Cursor/stream untuk baca besar (`QuerySet.iterator()`); jangan muat seluruh hasil ke memori.
- Batch terbatas + backpressure untuk pekerjaan massal (generate tagihan, payroll); bukan request-per-entitas (lihat `10-architecture.md`).
- Query baru pada tabel besar wajib dikawal `EXPLAIN (ANALYZE, BUFFERS)`; indeks mengikuti pola akses (composite dari kolom paling selektif, partial index untuk status aktif).
- Ledger terpartisi per periode; UNIQUE/PK pada tabel partisi harus memuat partition key (lihat `30-database.md`).

## Caching

- Cache hanya dengan TTL eksplisit dan invalidasi terdefinisi. Tanpa TTL = tidak di-cache.
- Data uang (tagihan, saldo, ledger) tidak di-cache secara optimistis; invalidasi lewat event/outbox bila perlu.
- SIAKAD boleh cache dengan TTL sesuai aturan integrasi (lihat `10-architecture.md`).

## Frontend (HTMX)

- Partial response kecil; kirim hanya fragment yang berubah (HTMX `hx-target`/`hx-swap`). Hindari render ulang seluruh halaman untuk aksi kecil.
- List besar (tagihan, jurnal, aging) memakai server-side pagination/sort/filter + virtualisasi bila perlu (lihat `50-frontend.md`).
- Uang dirender dengan filter `format_rupiah` (server) atau `Intl.NumberFormat('id-ID', ...)`; hindari re-render berantai.
- HTMX request debounced untuk search/filter; gunakan `hx-trigger="keyup changed delay:300ms"`.

## Verifikasi

- Perubahan yang menyentuh hot path wajib menyertakan benchmark before/after atau rencana pengukuran di ringkasan perubahan.
- Test konkurensi dan invarian ledger tetap lolos (lihat `70-testing.md`); optimasi tidak boleh melemahkan korektnes.