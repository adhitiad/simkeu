# P0 — Organization & RBAC

Status: skema dan layanan dasar. Data aktual, pejabat, struktur unit, matriks permission, dan masa jabatan harus diverifikasi terhadap dokumen resmi PTS dan badan penyelenggara.

## 1. Hierarki legal dan organisasi

~~~text
Entity (badan hukum penyelenggara / batas pelaporan)
├── Institution (satu atau lebih PTS)
│   ├── Campus
│   ├── Faculty
│   │   └── Study Program / Department / Laboratory
│   ├── Bureau
│   │   └── Section
│   │       └── Subsection
│   └── Support Unit / Business Unit
└── Institution lain (opsional)
~~~

Model yang digunakan dalam kode:

| Model | Makna | Aturan |
|---|---|---|
| Entity | Badan hukum penyelenggara dan batas buku besar/laporan | ID tetap BIGINT agar terhubung dengan ledger lama |
| Institution | Perguruan tinggi yang diselenggarakan Entity | Memiliki kode unik dalam Entity |
| OrganizationalUnit | Unit organisasi, pusat tanggung jawab, atau cost center | Parent harus dalam Entity dan Institution yang sama |
| Position | Katalog jabatan, bukan hak akses | Contoh Rektor, WR, Kabiro, Kabag, Bendahara |
| PositionAssignment | Penugasan seseorang pada jabatan/unit | Ada tanggal berlaku dan referensi SK |
| Role | Bundel hak akses aplikasi | Tidak sama dengan jabatan |
| Permission | Hak atomik yang dapat diuji service layer | Kode stabil seperti ledger.journal.read |
| UserRole | Penugasan Role ke pengguna pada scope | Bertanggal, dapat dicabut, dan tercatat di audit |

Entity pada implementasi awal diberi label “Badan hukum penyelenggara” karena telah dipakai oleh API/ledger dengan ID numerik. Penamaan class dan tabel tidak diubah pada P0 ini agar kompatibel. Jika satu badan hukum mengelola dua PTS, buat dua Institution dalam satu Entity. Fakultas, biro, program studi, dan kampus bukan badan hukum dan tidak memiliki ledger terpisah.

OrganizationalUnit mempertahankan nilai unit_type lama (university, faculty, department, unit) agar data existing tetap dapat dibaca. Nilai baru membedakan kampus, departemen, program studi, biro, bagian, subbagian, laboratorium, unit usaha, dan unit pendukung. Nilai lama tidak perlu dihapus dalam migrasi P0.

## 2. Jabatan vs hak akses

Jabatan mengikuti struktur organisasi dan SK pengangkatan. Role merupakan otorisasi digital yang diberikan berdasarkan tugas dan delegasi. Penugasan PositionAssignment tidak otomatis membuat UserRole.

Dengan pemisahan ini, Rektor dapat memiliki jabatan Rektor tetapi permission persetujuan transaksi tetap harus ditetapkan berdasarkan Statuta, SOP, limit nominal, sumber dana, dan delegasi yang berlaku. Role default dari perintah seed adalah template awal, bukan keputusan hukum atau matriks otorisasi final.

## 3. Scope RBAC dan inheritance

Tingkat akses UserRole.scope_level:

| Scope | Akses |
|---|---|
| entity | Seluruh institusi dan unit pada badan hukum |
| institution | Satu institusi dan unit di dalamnya |
| unit | Unit yang ditetapkan dan seluruh turunannya |

Aturan penolakan:
- Scope institusi tidak boleh digunakan untuk institusi lain di badan hukum yang sama.
- Scope unit tidak boleh mengakses unit saudara atau unit di institusi lain.
- Assignment yang belum mulai, kedaluwarsa, nonaktif, atau dicabut tidak memberi akses.
- is_staff bukan permission aplikasi. Pengecualian bootstrap awal yang sudah ada hanya boleh dipakai untuk penugasan admin pertama pada entitas kosong.
- Superuser adalah break-glass administratif; aksesnya harus dibatasi kepada operator tepercaya dan aktivitas sensitif tetap diaudit.

Pemeriksaan permission tersedia lewat apps.platform_app.services.has_permission() dan require_permission(). Pemanggil service wajib memasok entity_id dan, untuk akses terbatas, institution_id atau unit_id dari objek yang sedang diproses. Validasi di UI tidak menggantikan pemeriksaan service layer.

## 4. Integritas PostgreSQL

Migration P0 menambahkan trigger untuk mencegah:
- Institusi yang terhubung ke unit/penugasan milik badan hukum lain.
- Parent unit lintas badan hukum/institusi.
- Siklus dalam pohon unit organisasi.
- Assignment jabatan dengan Entity/Institution/Unit yang tidak konsisten.
- Role assignment dengan scope yang tidak sesuai Entity/Institution/Unit.

Tanggal efektif dan pencabutan disimpan di UserRole; histori tidak dihapus saat role dicabut. Audit event tetap append-only melalui migration sebelumnya. Constraint tanggal dan unique scope mencegah rentang tanggal tidak valid dan assignment duplikat pada scope yang sama.

## 5. Kompatibilitas dan batas P0

- Entity/OrganizationalUnit/UserRole lama dipertahankan dengan ID BIGINT. Jangan menggantinya dengan UUID pada P0.
- Migration mengubah assignment role lama dengan unit_id menjadi scope unit; assignment tanpa unit menjadi scope entity.
- PositionAssignment dan UserRole berbeda: perubahan jabatan tidak boleh otomatis mengubah permission tanpa proses IAM yang eksplisit.
- Antarmuka CRUD master data tersedia melalui Django Admin dan halaman platform yang sudah ada.
- Integrasi HR/SIAKAD/SIMPEG, SSO/MFA, workflow persetujuan, delegation limit, dan penggantian seluruh permission endpoint ledger masih menjadi pekerjaan lanjutan.
- Sebelum akses operator bisnis dibuka, seluruh endpoint laporan dan transaksi wajib dicek ulang agar filter Entity/Institution/Unit diterapkan pada query, bukan hanya tombol UI.

## 6. Master data yang wajib dikonfirmasi

Nama badan hukum, bentuk hukum, daftar PTS di bawah penyelenggara, struktur unit dan cost center, daftar jabatan, pemegang jabatan, tanggal SK, matriks permission per jabatan, serta delegasi nominal perlu diisi dari dokumen institusi. Data contoh dalam test bukan data operasional.
