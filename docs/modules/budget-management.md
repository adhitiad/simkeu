# P1 — Budget Management

Status: implementasi awal P1. Konfigurasi batas persetujuan dan pejabat tetap harus disahkan sesuai Statuta, AD/ART, SOP keuangan, dan delegasi badan penyelenggara.

## Cakupan

| Area | Implementasi |
|---|---|
| Tahun buku | Tahun buku per badan hukum, tanggal mulai/akhir, validasi overlap |
| RKAT | Dokumen per unit/cost center, multi-line RAB, tujuan, output, indikator, jadwal, akun COA, sumber dana, penanda dana terikat |
| RAPBU | Konsolidasi RKAT unit yang sudah disetujui ke dokumen entitas |
| APBU | Dibentuk dari RAPBU yang disetujui; setelah approval, APBU menjadi aktif dan pagu dibuka |
| Pagu | Alokasi aktif per baris APBU, unit, akun, sumber dana, tahun buku |
| Revisi | Permintaan perubahan satu/lebih alokasi, snapshot nominal sebelum/sesudah, alasan dan tanggal efektif |
| Komitmen | Reservasi anggaran berdasarkan sumber dokumen eksternal yang idempotent; pelepasan atau realisasi |
| Kontrol | UUIDv7, integer Rupiah, RBAC scope, maker-checker, row locking, audit event, transactional outbox |

## Alur operasional

1. Buat tahun buku untuk badan hukum melalui **Anggaran → Tambah tahun buku**.
2. Setiap unit membuat RKAT untuk tahun buku tersebut. Setiap baris minimal memiliki unit, akun COA aktif pada badan hukum yang sama, sumber dana, uraian, dan nominal Rupiah integer. Tujuan, output, indikator, serta jadwal dapat diisi untuk konteks rencana kegiatan.
3. Pemilik RKAT mengajukan dokumen. Reviewer yang berbeda dari pembuat/pengaju mencatat review; approver yang berbeda dari pembuat, pengaju, dan reviewer menyetujui RKAT.
4. Pengelola entitas mengonsolidasikan RKAT unit yang disetujui menjadi RAPBU. RAPBU menjalani proses submit, review, dan approval.
5. Dari RAPBU yang disetujui, pengelola membuat APBU. Setelah APBU melewati submit, review, dan approval, status APBU menjadi aktif dan baris APBU membentuk alokasi pagu.
6. Pengajuan pembelian/kontrak dapat membuat komitmen pada satu alokasi. Kombinasi source_type + source_id adalah idempotency key dalam satu badan hukum; retry payload identik mengembalikan komitmen yang sama, sedangkan penggunaan ulang key dengan payload berbeda ditolak.
7. Komitmen berstatus reserved atau fulfilled tetap mengurangi sisa pagu. Pelepasan komitmen memerlukan alasan dan aktor yang berbeda dari pembuat. Penandaan realisasi juga tidak boleh dilakukan oleh pembuat komitmen.
8. Revisi mencatat snapshot pagu sebelum/sesudah. Verifikator berbeda dari pembuat, approver berbeda dari pembuat dan verifikator. Approval menolak penurunan pagu di bawah jumlah komitmen aktif.

## Formula kontrol pagu

- komitmen_aktif = SUM(amount) dengan status reserved atau fulfilled.
- sisa_pagu = allocated_amount - komitmen_aktif.
- Reservasi mengunci row alokasi memakai SELECT ... FOR UPDATE; transaksi yang bersamaan tidak boleh sama-sama membelanjakan sisa pagu yang sama.
- Nominal disimpan sebagai integer Rupiah. Jangan mengirim float atau angka desimal ke service.
- Komitmen yang dilepas tidak lagi mengurangi sisa pagu. Komitmen fulfilled tetap mengurangi pagu karena merupakan realisasi penggunaan.

## Permission codes

Default permission ditambahkan melalui apps.platform_app.services.DEFAULT_ROLE_PERMISSIONS. Jalankan perintah seed setelah deploy agar role/permission default diperbarui:

    uv run python manage.py seed_rbac

Kode permission utama:
- budget.read, budget.plan.read, budget.plan.create
- budget.line.create, budget.plan.submit, budget.plan.review, budget.plan.approve
- budget.fiscal_year.manage, budget.pagu.read
- budget.revision.read, budget.revision.create, budget.revision.submit, budget.revision.verify, budget.revision.approve
- budget.commitment.read, budget.commitment.create, budget.commitment.release, budget.commitment.fulfill

Seed role adalah default awal, bukan matriks kewenangan final. Penugasan user tetap harus memiliki scope badan hukum/institusi/unit. Superuser adalah break-glass account dan tidak boleh dipakai untuk operasi harian.

## URL aplikasi

- /budgets/ — dashboard
- /budgets/fiscal-years/new/ — tahun buku
- /budgets/plans/new/ — RKAT draf
- /budgets/plans/<uuid>/ — detail rencana dan rincian
- /budgets/allocations/ — pagu aktif
- /budgets/revisions/new/ — ajukan revisi
- /budgets/revisions/<uuid>/ — review/approval revisi
- /budgets/commitments/ — komitmen
- /budgets/commitments/new/ — reservasi komitmen

## Tailwind + PostCSS

Dari root repository:

    npm install
    npm run css:build

Untuk pengembangan gunakan npm run css:watch. Sumber utility class ada pada template Django dan CSS komponen pada static/src/styles.css. Hasil build adalah static/css/app.css; build harus dijalankan pada pipeline deploy sebelum collectstatic.

## Batasan yang belum termasuk P1

- P1 belum mengirim jurnal ke ledger. Posting jurnal harus tetap lewat service apps.ledger.services.post setelah kebijakan pengakuan dan event sumber disepakati.
- Belum ada pengelolaan lampiran/dokumen bukti, vendor/pengadaan, purchase request, kontrak, pembayaran, SPJ, pajak, atau rekonsiliasi.
- Workflow saat ini adalah state machine dan permission RBAC; matriks limit nominal, delegasi, SLA, dan routing approver dinamis belum dikonfigurasi sebagai workflow engine.
- Dashboard menampilkan ringkasan untuk tahun buku terpilih; report formal dan snapshot pengesahan masih berada pada tahap berikutnya.
- Penguncian database dan migrasi ditujukan ke PostgreSQL. Jangan mengganti database production dengan SQLite untuk modul ini.

Sebelum digunakan pada data keuangan nyata, jalankan migration/test di PostgreSQL staging dan minta review kebijakan keuangan oleh pejabat serta akuntan/auditor yang berwenang.
