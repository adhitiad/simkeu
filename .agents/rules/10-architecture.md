---
description: Arsitektur modular monolith Django, boundary modul, event/outbox, integrasi SIAKAD/SIMPEG, observability.
globs: ["services/**", "apps/**", "packages/**"]
alwaysApply: false
---
# 10 — Architecture

## Bentuk sistem

- **Modular monolith** (Django). Modul sebagai Django apps: `billing`, `payment`, `ledger`, `budget`, `academic` (ACL ke SIAKAD/SIMPEG), `platform` (auth, audit, config, outbox). Ekstraksi ke service terpisah hanya dengan kebutuhan skala yang terukur.
- Satu schema PostgreSQL per modul (`billing.*`, `payment.*`, `ledger.*`, `budget.*`). **Dilarang** query atau join lintas schema modul lain. Akses data modul lain hanya lewat interface publik paketnya atau event.
- `ledger.post(ctx, Journal)` adalah **satu-satunya jalur tulis** ke ledger. Modul lain tidak pernah insert ke tabel ledger.
- Layering: `view → service → repository`. Domain tidak mengimpor Django ORM, `HttpRequest`, atau library transport. Service menerima data primitif/DTO, bukan model Django.

## Event dan outbox

- Event ditulis ke tabel `platform.outbox` **dalam transaksi yang sama** dengan perubahan state. Relay (Celery/RQ) mengirim at-least-once.
- Konsumen idempotent: dedupe berdasarkan `event_id`. Gagal berulang masuk DLQ dengan alasan tersimpan.
- Skema event berversi (`type`, `version`). Perubahan breaking = versi baru, bukan mutasi.

## Integrasi SIAKAD dan SIMPEG

- Lewat anti-corruption layer di modul `academic`. Simpan read model minimal (mis. `student_id`, prodi, status, `employee_id`). Jangan menduplikasi master data.
- Status bayar untuk gating (KRS/UTS/UAS/KHS/wisuda) dipublikasikan sebagai event dan endpoint query. SIAKAD boleh cache dengan TTL.
- Kebijakan fail-open/fail-closed saat layanan tidak terjangkau adalah keputusan bisnis: jadikan konfigurasi, jangan hardcode.
- Pemanggilan eksternal: timeout eksplisit, retry dengan backoff + jitter hanya untuk operasi idempotent, circuit breaker.

## Multi-entity

- Semua tabel keuangan membawa `entity_id` (yayasan/universitas). COA per entity. Konsolidasi dilakukan di layer pelaporan, bukan dengan menggabungkan data di tabel transaksi.

## Skalabilitas dan memori

- Service stateless. State di PostgreSQL (dan cache bila dibutuhkan).
- Pekerjaan massal (generate tagihan, rekonsiliasi, payroll) lewat task queue dan worker pool dengan batch size terbatas dan backpressure. Bukan request-per-entitas.
- Baca data besar dengan cursor/stream (`QuerySet.iterator()`). Jangan muat seluruh hasil query ke memori.

## Observability

- Logging terstruktur JSON (`structlog` atau `logging` + formatter JSON). Setiap request/job membawa `request_id` dan `trace_id` (OpenTelemetry).
- Metrik RED per endpoint/job. Audit log terpisah dari log aplikasi (lihat `60-security.md`).

## Health endpoint

- `/healthz` (liveness): hanya membuktikan proses hidup. **Tanpa** cek dependency (DB, SIAKAD, SIMPEG, storage) — dependensi lambat/mati tidak boleh memicu restart container berantai.
- `/readyz` (readiness): cek DB (`SELECT 1`) dan dependency kritis dengan timeout pendek (±2–3 detik); gagal = HTTP 503. Dipakai load balancer/orchestrator untuk berhenti mengirim traffic, bukan untuk restart.
- Keduanya: ringkas, idempoten, tidak menulis state, tidak memerlukan auth, dan **tidak membocorkan** versi, konfigurasi, DSN, atau nama dependency internal — body cukup `ok`/`unavailable` + status per dependency secara generik.
- Jangan pakai health endpoint sebagai metrik bisnis; metrik RED tetap lewat Prometheus/OTel.

## Konfigurasi

- 12-factor: konfigurasi dari environment, divalidasi saat startup (fail fast).
- Kebijakan bisnis yang berubah (denda, dispensasi, tarif pajak) disimpan sebagai data berversi dengan `effective_from`, bukan konstanta di kode.