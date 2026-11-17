---
description: Frontend — Django templates, HTMX, Tailwind CSS, aksesibilitas.
globs: ["templates/**", "static/**", "apps/**/templates/**", "**/*.html"]
alwaysApply: false
---
# 50 — Frontend (Django + HTMX)

## Prinsip umum

- Server-rendered. Django templates + HTMX untuk interaksi parsial. Tidak ada SPA/React/Vue.
- Semua logika bisnis di server (Django). Template hanya presentasi. Tidak ada logika billing/payment/ledger di JS.
- Teks UI Bahasa Indonesia, terpusat (template tags/i18n), bukan string tersebar.

## TypeScript/JS

- JS minimal (Alpine.js bila perlu). Tanpa `any` implisit; gunakan JSDoc bila file JS terpisah. Prefer HTMX attributes daripada JS kustom.
- Data tak dipercaya bertipe `unknown` lalu divalidasi. Switch atas union wajib exhaustive.

## HTMX

- Partial response berupa fragment HTML (template partial). Gunakan `hx-target`, `hx-swap`, `hx-trigger` secara eksplisit.
- Request finansial (bayar, void, refund, tutup periode) mengirim header idempotency key yang dibuat **sekali per niat pengguna** (bukan per retry), dan **tanpa optimistic update** untuk data uang.
- Mutasi uang tidak auto-retry di client; tampilkan error dan `request_id`.
- Gunakan `hx-indicator` untuk status loading; jangan blokir UI tanpa feedback.
- Search/filter: `hx-trigger="keyup changed delay:300ms"` + server-side pagination/sort/filter.
- Error handling: kembalikan fragment error dengan status HTTP yang sesuai; HTMX `hx-on::response-error` untuk tampilan.

## Validasi

- Validasi server (Django forms/serializer) otoritatif. Validasi client (HTML5 attributes) hanya untuk UX.
- Uang: integer Rupiah. Validasi `int` di server; jangan terima desimal dari form tanpa konversi eksplisit.
- ID: UUID dengan validasi. Status: enum yang sinkron dengan DB/Python.

## Aksesibilitas (wajib)

- Label, `aria-*`, navigasi keyboard, fokus terlihat.
- Aksi destruktif/finansial (void, refund, tutup periode) memakai dialog konfirmasi yang menyebut nominal dan target.
- Gunakan komponen dasar yang konsisten (Tailwind + partials).

## Tailwind CSS

- Utility classes; hindari CSS ad hoc. Komponen berulang diekstrak ke partial template.
- Build CSS via pipeline proyek (npm atau django-tailwind) — lihat Keputusan terbuka.

## Format dan UI

- Uang: filter template `format_rupiah` atau `Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 })`.
- Tanggal: `Intl.DateTimeFormat` dengan `timeZone: 'Asia/Jakarta'` atau filter server dengan zona WIB.
- Kolom uang rata kanan, `tabular-nums`.
- Code-split tidak berlaku; gunakan partial loading via HTMX untuk bagian berat.
- Tampilkan `request_id` pada pesan error agar dapat ditelusuri.