# Model Tata Kelola dan Arsitektur SIMKEU untuk PTS

Status: rancangan target. Kewenangan, limit nominal, dan kebijakan akuntansi final wajib disahkan berdasarkan Statuta, AD/ART, SOP keuangan, serta arahan akuntan/auditor.

## 1. Konteks PTS

PTS didirikan oleh masyarakat melalui badan penyelenggara berbadan hukum yang berprinsip nirlaba. Badan penyelenggara dapat berbentuk yayasan, perkumpulan, atau bentuk lain sesuai ketentuan. PTS wajib memiliki Statuta. Pengelolaan nonakademik PTS, termasuk keuangan, mengikuti pengaturan badan penyelenggara dan ketentuan yang berlaku.

Rektor memimpin perguruan tinggi sesuai Statuta dan delegasi. Pembina, Pengurus, dan Pengawas menjalankan kewenangan badan hukum yayasan sesuai AD/ART dan peraturan. SIMKEU tidak boleh menganggap Rektor otomatis merupakan organ badan hukum yayasan.

## 2. Pisahkan badan hukum, institusi, dan pusat anggaran

LegalEntity adalah badan hukum yang memiliki aset, kewajiban, kontrak, rekening, dan laporan keuangan. Institution adalah PTS/universitas yang diselenggarakan. OrganizationUnit adalah pusat tanggung jawab/anggaran seperti fakultas, program studi, biro, bagian, unit usaha, laboratorium, atau kampus.

~~~text
Badan Hukum Penyelenggara (LegalEntity)
├── Perguruan Tinggi A (Institution)
│   ├── Kampus
│   ├── Fakultas → Program Studi / Laboratorium
│   ├── Biro Keuangan dan Umum
│   │   ├── Bagian Keuangan
│   │   ├── Subbagian Verifikasi
│   │   ├── Bendahara
│   │   └── Pendapatan
│   └── Unit pendukung / unit usaha
└── Perguruan Tinggi B (opsional, bila satu badan hukum mengelola lebih dari satu PTS)
~~~

Aturan:
- entity_id pada ledger yang sudah ada berarti identitas badan hukum pelapor, bukan ID fakultas, kampus, atau cost center.
- Jangan membuat ledger terpisah hanya karena ada fakultas atau kampus. Gunakan dimensi organisasi dan pusat biaya pada dokumen dan baris jurnal.
- Bila ada badan hukum lain yang benar-benar terpisah, buat LegalEntity dan buku besar terpisah. Konsolidasi dilakukan di reporting layer dengan eliminasi transaksi antar-entitas.
- Bila dokumen hukum menunjukkan pola berbeda, konfigurasi hirarki harus mengikuti dokumen tersebut.

### Master data yang diperlukan

| Entitas | Fungsi |
|---|---|
| LegalEntity | Badan hukum, NPWP, alamat, tahun buku, standar akuntansi |
| Institution | PTS/universitas yang diselenggarakan badan hukum |
| OrganizationUnit | Struktur unit hierarkis dan atasan |
| PositionAssignment | Penempatan jabatan, tanggal berlaku, unit, delegasi |
| RoleAssignment | Peran sistem dan scope data |
| DelegationRule | Batas kewenangan per jenis transaksi, nominal, sumber dana, periode |
| FiscalYear | Tahun buku badan hukum |
| AcademicTerm | Tahun akademik/semester; terpisah dari tahun buku |
| CostCenter | Unit penanggung jawab anggaran |
| ProgramActivity | Pendidikan, penelitian, PkM, aktivitas pendukung |
| FundingSource | Pendidikan, hibah, donasi, penelitian, unit usaha, dan lain-lain |
| FundRestriction | Syarat dan tujuan penggunaan dana |
| AccountingPolicyVersion | Kebijakan akuntansi dan tanggal efektif |
| ReportProfile | Standar/paket laporan dan mapping akun |

Jabatan dan penugasan harus berversi waktu. User dapat memiliki lebih dari satu peran, tetapi setiap tindakan dievaluasi terhadap scope dan delegasi yang aktif saat tindakan terjadi.

## 3. Dimensi transaksi

Satu transaksi harus dapat dianalisis menurut akun natural/COA, badan hukum, institusi, unit/cost center, program/aktivitas, sumber dana, pembatasan dana, kampus, tahun buku, periode akuntansi, dan tahun akademik/semester bila relevan. Simpan dimensi yang diperlukan pada dokumen sumber dan baris jurnal; jangan menyimpulkan semua dimensi hanya dari akun COA.

## 4. Arsitektur modular target

Pertahankan Django modular monolith dan PostgreSQL. Jangan memecah microservice sebelum ada kebutuhan skala yang terukur.

| Bounded context | Tanggung jawab |
|---|---|
| organization (baru) | Legal entity, institusi, unit, jabatan, scope, delegasi |
| budget | RKAT, pagu, alokasi, revisi, komitmen, realisasi |
| billing | Tagihan pendidikan/nonpendidikan, tarif, beasiswa, dispensasi |
| payment | Penerimaan, alokasi, settlement, refund, rekonsiliasi provider |
| expenditure (baru) | Pengajuan pengeluaran, pengadaan, utang, pembayaran keluar |
| verification (baru) | Checklist, pemeriksaan dokumen, koreksi, SPJ |
| workflow (baru) | Definisi alur, approval task, delegasi, SLA, histori |
| treasury (baru) | Kas, bank, kas kecil, rekening, rekonsiliasi |
| ledger | COA, periode, jurnal, buku besar, trial balance |
| reporting (baru) | Laporan manajemen, laporan badan hukum, ekspor, snapshot |
| documents (baru) | Metadata, versi, akses dokumen, signed URL |
| academic | Anti-corruption layer SIAKAD/SIMPEG |
| platform | Auth, audit, outbox, konfigurasi |
| ai_assistant (baru) | OpenRouter gateway dan analisis terkontrol |

Dependency satu arah: view/API → application service → domain/repository. Modul lain menulis ke ledger hanya melalui ledger.post(...). Integrasi lintas modul memakai interface/event outbox, bukan query lintas schema.

## 5. Peran dan otorisasi

| Peran | Fokus |
|---|---|
| Rektor | Dashboard eksekutif; review/persetujuan sesuai Statuta/delegasi |
| Wakil Rektor | Review program, prioritas, dan usulan anggaran sesuai bidang/delegasi |
| Kabiro Keuangan & Umum | Pengendalian proses, review lintas bagian, risiko dan kepatuhan |
| Kabag Keuangan | Operasional, pemeriksaan administrasi, kontrol anggaran, laporan |
| Bendahara | Penerimaan/pengeluaran kas-bank; bukan penyetuju transaksi yang dibuat sendiri |
| Kasubbag Verifikasi | Kelengkapan, validitas, kepatuhan, pajak/dokumen, SPJ |
| Pendapatan | Tagihan, pencatatan penerimaan, alokasi, exception pendapatan |
| Pengelola badan penyelenggara | Review/persetujuan sesuai AD/ART dan delegasi; role terpisah |
| Auditor internal/SPI | Read-only terkontrol ke laporan, dokumen, audit trail |

Role bukan jabatan permanen yang ditanam di kode. Role berasal dari penugasan aktif, scope unit, jenis transaksi, batas nominal, dan delegasi. is_staff bukan otorisasi bisnis yang cukup.

## 6. Kontrol internal

1. Maker-checker: pembuat berbeda dari verifikator/penyetuju.
2. Separation of duties: pemohon, verifikator, approver, dan pelaksana pembayaran tidak boleh seluruhnya orang yang sama.
3. Budget reservation: komitmen dibentuk saat pengajuan disetujui, bukan menunggu kas keluar.
4. Accrual: pengakuan beban/aset/utang mengikuti kebijakan dan kejadian ekonomi, bukan hanya tanggal transfer bank.
5. Transaksi/jurnal posted tidak diedit/dihapus; koreksi memakai reversal/adjustment.
6. Periode tertutup menolak posting.
7. Audit trail menyimpan before/after, actor, waktu, alasan, request ID, dokumen sumber, approval, versi kebijakan.
8. Dana terikat hanya boleh digunakan sesuai tujuan dan syaratnya.
9. Rekonsiliasi bank diperiksa pihak yang terpisah dari pembuat/pembayar transaksi.
10. Laporan disahkan disimpan sebagai snapshot immutable.

## 7. AI OpenRouter

AI menerima data agregat/terpilih yang sudah disaring service berdasarkan scope aktor. AI tidak menerima kredensial database dan tidak membuat SQL bebas.

AI boleh membuat ringkasan RKAT, narasi variance, analisis tren, draft surat, dan saran klasifikasi dokumen. AI tidak boleh menyetujui pengajuan, menjalankan transfer, membuat jurnal, mengubah COA/periode, atau menentukan angka dari inferensi. Setiap angka harus merujuk periode, filter, waktu data, dan ID sumber laporan. Draft AI harus ditinjau manusia.

## 8. Keputusan sebelum production

- Bentuk badan penyelenggara dan jumlah badan hukum.
- Statuta, AD/ART, SOP, struktur organisasi, matriks delegasi.
- Tahun buku, basis akuntansi, standar SAK, kebijakan pengakuan pendapatan/hibah/beasiswa/aset.
- COA, dimensi, restriction, unit pelaporan, konsolidasi.
- Limit nominal dan pejabat pengesah RKAT, revisi, pengeluaran, refund, laporan tahunan.
- Bank/payment provider, rekening koran, dokumen pajak.
- Retensi dokumen dan klasifikasi data yang boleh diproses OpenRouter.
