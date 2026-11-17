---
description: Prinsip kerja inti dan Definition of Done. Berlaku untuk semua tugas.
alwaysApply: true
---
# 00 — Core

## 10 prinsip (wajib di setiap perubahan)

1. **Architecture**: modul terisolasi, dependency searah (handler → service → repository). Rancang untuk skala: stream dan batch, bukan load-all. Keyset pagination untuk data besar.
2. **Optimization**: ukur sebelum optimasi (`py-spy`, `pytest-benchmark`, `EXPLAIN (ANALYZE, BUFFERS)`). Hot path: bulk billing, webhook, alokasi pembayaran, posting ledger. N+1 dilarang.
3. **Types**: strict typing mutlak. Python tanpa `Any` di API domain (boleh hanya di batas serialisasi). Semua fungsi bertipe, lolos `mypy --strict` atau pyright strict. HTMX/JS tanpa `any` implisit.
4. **Concurrency**: paralelisme hanya dengan batas eksplisit (worker pool Celery/RQ, `asyncio.Semaphore`), context cancellation, dan bebas race (test konkurensi pytest).
5. **Edge cases**: sebelum menulis kode, daftar kasus: input kosong/ekstrem, duplikasi, out-of-order, retry, partial failure, concurrent update, periode tertutup, nilai nol/negatif, zona waktu.
6. **Security**: ikuti `60-security.md`. Tidak ada kode dengan celah yang diketahui.
7. **Error handling**: error eksplisit di-wrap dengan konteks. Log terstruktur satu kali di batas (handler/worker). Tidak ada silent fail.
8. **Modularity**: DRY tanpa abstraksi prematur (rule of three). Dependency injection via constructor. Interface didefinisikan di sisi konsumen. Semua unit dapat di-test terisolasi.
9. **Pragmatism**: trade-off dan batasan teknis dipaparkan dalam bullet singkat di ringkasan perubahan.
10. **Execution**: hanya kode yang compile dan siap deploy. Tanpa `TODO`, placeholder, pseudo-code, atau elipsis di dalam kode. Info kurang: nyatakan asumsi eksplisit atau ajukan satu pertanyaan.

## Definition of Done

- Build, lint, typecheck, dan test lolos (lihat `AGENTS.md`).
- Test baru untuk perilaku baru dan edge case-nya.
- Migrasi up dan down terverifikasi (bila ada).
- Tidak ada `Any`, `# type: ignore`, `_ = err`/`except: pass`, `sys.exit` di request path, secret, atau PII di log.
- Kontrak API dan dokumentasi singkat modul diperbarui.

## Batas perubahan

- Jangan ubah migrasi yang sudah diterapkan. Perbaikan = migrasi baru (forward-only).
- Jangan refactor di luar scope tugas.
- Jangan tambah dependency tanpa alasan tertulis (ukuran, maintenance, lisensi, alternatif stdlib).
- Jangan melemahkan test, lint, atau tipe agar build lolos.

## Format ringkasan ke pengguna

Perubahan · Trade-off (bullet) · Risiko/asumsi · Cara verifikasi. Tanpa preamble, tanpa permintaan maaf.
