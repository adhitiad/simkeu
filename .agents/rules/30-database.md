---
description: PostgreSQL dan Django migrations — konvensi skema, migrasi, ledger immutable, partisi, locking, indeks.
globs: ["**/migrations/**", "**/*.sql", "db/**"]
alwaysApply: false
---
# 30 — Database (PostgreSQL + Django migrations)

## Migrasi Django

- Lokasi per app Django: `<app>/migrations/`, format Python. Buat dengan `python manage.py makemigrations <app>` (sequential, auto-numbered).
- Migrasi yang sudah diterapkan **tidak boleh diubah**. Koreksi = migrasi baru.
- Setiap migrasi punya `forwards` dan `backwards` (RunPython/RunSQL dengan `reverse_sql`) yang bekerja. Verifikasi `migrate` lalu `migrate <app> <prev>` lalu `migrate` di database lokal/CI.
- Fungsi dan trigger DB (append-only, period lock) ditulis lewat `RunSQL` dengan `-- +...` tidak berlaku; gunakan `migrations.RunSQL` dengan SQL mentah dan `reverse_sql`. `CREATE INDEX CONCURRENTLY` tidak bisa di dalam transaksi; set `atomic = False` pada migration.
- Perubahan aman untuk deploy bertahap (expand → migrate data → contract). Tidak ada `DROP COLUMN` atau rename dalam satu rilis dengan kode yang masih memakainya.
- Migrasi data besar dikerjakan per batch, tidak menahan lock panjang di tabel panas.

## Konvensi skema

- Satu schema per modul. Nama `snake_case`, tabel jamak, FK eksplisit.
- Waktu: `timestamptz` (UTC). Tanggal akuntansi/jatuh tempo: `date` (zona Asia/Jakarta). Tidak ada `timestamp` tanpa zona.
- Uang: `bigint` (Rupiah utuh) dengan `CHECK` sesuai semantik (mis. `amount >= 0`). Tidak ada `numeric`/`float` untuk uang.
- PK: UUIDv7 (dibuat di aplikasi) untuk entitas. `ledger_entries` boleh memakai `bigint generated always as identity` untuk urutan dan indeks ringkas.
- Semua tabel keuangan: `entity_id`, `created_at`, `created_by`. Constraint (`NOT NULL`, `CHECK`, `UNIQUE`, FK) menjadi penjaga terakhir, bukan hanya validasi aplikasi.
- Status berupa `text` + `CHECK (status IN (...))` atau enum PG. Daftar nilai sinkron dengan konstanta Python (Enum) dan (bila ada) skema kontrak.

## Ledger

- `ledger_entries` append-only. Tolak `UPDATE/DELETE` di level DB dan cabut hak dari role aplikasi:

```sql
-- (Dijalankan via migrations.RunSQL; reverse_sql menyediakan rollback)
CREATE OR REPLACE FUNCTION ledger.reject_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'ledger_entries is append-only (op=%)', TG_OP
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ledger_entries_append_only
BEFORE UPDATE OR DELETE ON ledger.ledger_entries
FOR EACH ROW EXECUTE FUNCTION ledger.reject_mutation();

REVOKE UPDATE, DELETE, TRUNCATE ON ledger.ledger_entries FROM app_rw;
```

- Invarian `SUM(debit) = SUM(credit)` per jurnal ditegakkan di DB (constraint trigger `DEFERRABLE INITIALLY DEFERRED`) **dan** di aplikasi. Verifikasi dukungannya pada tabel partisi di versi PostgreSQL yang dipakai.
- **Period lock**: insert ke periode tertutup ditolak di DB (trigger/constraint). Koreksi pada periode tertutup = jurnal pembalik di periode terbuka.
- Saldo materialized per akun/periode wajib bisa direkonstruksi dari ledger. Sediakan job verifikasi (agregat ledger = saldo materialized); selisih memicu alert.

## Partisi

- Partisi `ledger_entries` per periode (range). Rencanakan pembuatan partisi berikutnya secara otomatis dan alert bila partisi mendatang belum ada.
- Pada tabel partisi, `UNIQUE`/PK **harus memuat kolom partition key**. Karena itu idempotency (`UNIQUE (provider, provider_ref)`) ditaruh di tabel **tidak dipartisi** (mis. `payment.inbox`).

## Query dan indeks

- Semua query baru yang menyentuh tabel besar dicek dengan `EXPLAIN (ANALYZE, BUFFERS)`. Indeks sesuai pola akses (composite berurutan dari kolom paling selektif, partial index untuk status aktif).
- Keyset pagination (`WHERE (created_at, id) < (?, ?) ORDER BY created_at DESC, id DESC LIMIT n`) untuk daftar besar. Hindari `OFFSET` besar.
- Locking: `SELECT ... FOR UPDATE` dengan urutan kunci deterministik. `FOR UPDATE SKIP LOCKED` untuk worker yang mengambil job dari tabel.
- Parameterized query saja. Tidak ada interpolasi string ke SQL.

## Hak akses

- Role terpisah: `app_rw` (aplikasi), `migrator` (Django migration runner, DDL), `reporting_ro` (read-only). Aplikasi tidak memakai role pemilik skema.
