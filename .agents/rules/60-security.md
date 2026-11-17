---
description: Keamanan berlapis — authn/z, RBAC, maker-checker, webhook, PII, secret, audit, upload.
alwaysApply: true
---
# 60 — Security

## Autentikasi dan otorisasi

- Deny-by-default. Otorisasi ditegakkan di **service layer**, bukan hanya di route/UI.
- RBAC dengan scope data (entity, fakultas, prodi, unit). Query selalu dibatasi scope aktor.
- **Maker-checker** untuk: jurnal manual, perubahan tarif, dispensasi, refund, penghapusan piutang, tutup/buka periode. Pembuat ≠ penyetuju, ditegakkan di service dan constraint DB.
- Token berumur pendek, rotasi refresh token. Cookie session: `HttpOnly`, `Secure`, `SameSite`; lindungi dari CSRF.
- Rate limiting pada login, pencarian, dan endpoint publik. CORS allowlist eksplisit. Security headers (CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`).

## Webhook dan integrasi

- Verifikasi signature (HMAC) dengan perbandingan constant-time, toleransi timestamp, batas ukuran body. Gunakan allowlist IP bila provider mendukung.
- Jangan percaya nominal/status dari callback begitu saja: cocokkan dengan tagihan. Tidak cocok = karantina (lihat `40-domain-keuangan.md`).
- Kredensial provider per environment, dirotasi, tidak pernah di repo.

## Data sensitif

- PII (NIK, nomor rekening, kontak) dienkripsi di level field saat disimpan. Kunci di KMS/secret manager. Tampilan dimask secara default.
- Tidak ada PII, token, atau secret di log, error message ke klien, atau URL. Patuhi UU Pelindungan Data Pribadi (UU No. 27 Tahun 2022): minimisasi data, retensi terdefinisi.
- Secret hanya dari environment/secret manager. Template ada di `.env/*.example` tanpa nilai nyata. Jangan commit `.env/.env` atau `.env/.env.<APP_ENV>`; keduanya sudah diabaikan git.

## Injeksi dan input

- SQL parameterized saja (Django ORM / `cursor.execute` dengan parameter). Tidak ada string concat ke query.
- Validasi dan batasi semua input di server (panjang, rentang, format, enum). Tolak field tak dikenal pada payload kritis.
- Output HTML tidak pernah dibangun dari string mentah; gunakan escaping bawaan framework. Tidak ada `dangerouslySetInnerHTML` kecuali konten tersanitasi.

## Upload (bukti bayar, dokumen)

- Validasi tipe dengan magic bytes, bukan ekstensi/`Content-Type` klien. Batas ukuran. Nama file diganti (UUID). Simpan di object storage privat, akses via signed URL berumur pendek.

## Audit

- Audit log append-only: aktor, aksi, entitas, `before/after`, `request_id`, waktu, IP. Aksi finansial dan perubahan hak akses **wajib** tercatat. Terpisah dari log aplikasi dan tidak dapat diubah oleh role aplikasi.

## Supply chain

- `pip-audit`/`bandit` dan pemindai dependency JS (mis. `osv-scanner`/`npm audit`) di CI. Pin versi, review dependency baru. Image container minimal, non-root.

## OWASP Top 10:2025 (rujukan baseline)

Terbaru: **OWASP Top 10:2025** (`top10.owasp.org/2025`). Semua desain/review keamanan mengacu ke daftar ini:

| ID | Kategori | Kendali utama di repo ini |
|---|---|---|
| A01:2025 | Broken Access Control | Deny-by-default, otorisasi di service layer, scope entity/fakultas/prodi, maker-checker |
| A02:2025 | Security Misconfiguration | 12-factor config, security headers, CORS allowlist, non-root container, tanpa kredensial default |
| A03:2025 | Software Supply Chain Failures | `pip-audit`/`bandit`, `osv-scanner`/`npm audit`, pin versi, review dependency baru |
| A04:2025 | Cryptographic Failures | TLS 1.2+ (1.3 bila bisa), field-level encryption + KMS, hash password kuat, tanpa kripto buatan sendiri |
| A05:2025 | Injection | Parameterized query saja, validasi/batas input di server, escape output framework |
| A06:2025 | Insecure Design | Threat model + daftar edge case sebelum coding (lihat `00-core.md`), rate limiting, abuse case |
| A07:2025 | Authentication Failures | Token pendek + rotasi refresh, cookie HttpOnly/Secure/SameSite, rate limit login, MFA bila tersedia |
| A08:2025 | Software or Data Integrity Failures | Verifikasi signature webhook (HMAC, constant-time), verify image/dependency, CI dengan least privilege |
| A09:2025 | Security Logging and Alerting Failures | Audit log append-only terpisah, `request_id`/`trace_id` di log, alert pada anomali (gagal login massal, selisih rekonsiliasi) |
| A10:2025 | Mishandling of Exceptional Conditions | Error eksplisit, tidak ada silent fail, stack trace tidak bocor ke klien, fail-closed untuk aksi finansial, timeout di semua I/O |

## OWASP ZAP (DAST)

- CI menjalankan **ZAP Baseline Scan** (`zap-baseline.py`) terhadap environment staging pada setiap rilis/PR ke main; **ZAP Full Scan** (`zap-full-scan.py`) terjadwal (mis. mingguan) di luar jam sibuk.
- ZAP hanya melawan staging dengan data sintetis — **tidak pernah** melawan production dengan payload aktif/serangan nyata.
- Kebijakan ambang: alert **High** menggagalkan build; **Medium** wajib tiket + perbaikan dalam SLA yang disepakati; Low/Informational dicatat dan ditinjau berkala.
- Laporan ZAP (HTML/JSON) disimpan sebagai artefak CI; temuan diverifikasi ulang (re-scan) setelah perbaikan.
- ZAP melengkapi, bukan menggantikan, SCA (`pip-audit`/`bandit`/`osv-scanner`) dan review manual — DAST tidak menjangkau logika bisnis (mis. maker = checker).
- Kegagalan ZAP karena false positive ditandai via file konteks/alert filter yang di-review, bukan dengan menurunkan ambang severity.
