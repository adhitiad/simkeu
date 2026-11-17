---
description: Aturan Python dan Django — tipe, error, context, concurrency, logging, transaksi, ORM.
globs: ["**/*.py"]
alwaysApply: false
---
# 20 — Python dan Django

## Tipe dan struktur

- Nominal uang: `Rupiah = int` (alias tipe; validasi `isinstance(x, int)` dan bukan `bool` di batas input). Tidak ada `float` untuk uang. Operasi proporsional (proration, persen, denda) lewat satu fungsi dengan kebijakan pembulatan eksplisit dan test tabel.
- ID bertipe kuat (`StudentID = NewType("StudentID", UUID)` dkk.), bukan `str` mentah.
- Status/enum: `enum.Enum`/`enum.StrEnum` dengan konstanta + `match`/`if` exhaustive. Transisi state divalidasi di satu tempat.
- Hindari `Any` di API domain. Gunakan generics atau tipe konkret. `Any` hanya di batas serialisasi (JSON).
- Konstruktor/factory eksplisit; dependency lewat parameter (constructor injection), bukan global. Tidak ada side effect di import.
- Semua fungsi publik memiliki anotasi tipe; lolos `mypy --strict` atau pyright strict.

## Error

- Selalu wrap dengan konteks: `raise DomainError(f"allocate payment {payment_id}") from err`.
- Error domain berupa exception khusus (`InvoiceVoidError`, `PeriodClosedError`, `DuplicatePaymentError`). View memetakan error domain ke status HTTP di satu tempat.
- Dilarang: `except: pass`, `_ = err`, `sys.exit` di request/job path, `print` di production.
- Log error **sekali**, di batas (view/worker), dengan field terstruktur. Jangan log lalu raise error yang sama di setiap layer.

## Context dan I/O

- Timeout eksplisit pada setiap panggilan eksternal dan query yang berpotensi lama (`requests`/`httpx` dengan `timeout=`).
- Gunakan context manager untuk transaksi dan resource.

## Concurrency

- Setiap task Celery/RQ punya penanganan error dan retry terbatas. Tidak ada fire-and-forget tanpa pelacakan.
- Paralelisme terbatas: worker pool dengan concurrency terkonfigurasi. Tidak ada thread per item tanpa batas.
- Konkurensi pada saldo/alokasi diselesaikan di database (locking atau isolation), bukan lock proses.

## Logging

- Logging terstruktur JSON. Field baku: `request_id`, `trace_id`, `entity_id`, `actor_id`.
- Dilarang mencetak PII (NIK, nomor rekening, token) ke log. Gunakan masking.

## Django ORM

- Repository membungkus ORM di belakang interface/fungsi. Paket domain tidak mengimpor `django.db.models` atau `HttpRequest`.
- **Dilarang** `migrate --runsyncdb` di production; skema milik Django migrations (lihat `30-database.md`).
- **Dilarang** soft delete (`is_deleted`) pada tabel finansial. Gunakan kolom status (`void`, `reversed`) dan jurnal pembalik.
- Gunakan `select_related`/`prefetch_related` terukur; hindari N+1. `QuerySet` tanpa batas pada tabel besar dilarang; gunakan `.iterator()`/pagination.
- Jangan taruh logika bisnis di signal (`post_save` dkk.). Logika di service.
- Query ledger, alokasi pembayaran, dan laporan berat: SQL eksplisit (`raw()`/`cursor.execute` dengan parameter). Tidak pernah string concat.
- Transaksi eksplisit dengan locking untuk alur yang mengubah saldo/alokasi:

```python
from django.db import transaction

def allocate(self, req: AllocateRequest) -> None:
    with transaction.atomic():
        account = Account.objects.select_for_update().get(id=req.account_id)
        # ... alokasi deterministik, lalu ledger.post dalam transaksi yang sama
```

- Bila memakai isolation serializable, tangani serialization failure dengan retry terbatas (mis. 3x, backoff + jitter). Operasi di dalam transaksi harus aman untuk diulang.
- Kunci selalu diambil dengan urutan deterministik (mis. urut `id`) untuk mencegah deadlock.

## Lint (minimal)

`ruff` (E, F, I, B, UP, SIM, RUF), `mypy --strict`, `bandit`, `pip-audit`. Tidak ada `# type: ignore` tanpa alasan.