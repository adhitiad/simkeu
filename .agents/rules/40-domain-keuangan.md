---
description: Aturan domain keuangan PTS — glosarium, billing, pembayaran, alokasi, ledger, pajak, periode.
globs: ["services/**", "db/**", "packages/contracts/**"]
alwaysApply: false
---
# 40 — Domain Keuangan PTS

## Glosarium (UI: Indonesia, kode: English)

| Indonesia | Kode |
|---|---|
| tagihan | `invoice` |
| pembayaran | `payment` |
| jurnal / buku besar | `journal` / `ledger` |
| akun, COA | `account`, `chart_of_accounts` |
| periode | `period` |
| tarif | `fee_schedule` |
| potongan, beasiswa | `discount`, `scholarship` |
| dispensasi | `waiver` |
| cicilan, denda | `installment`, `penalty` |
| pengajuan dana, SPJ | `fund_request`, `accountability_report` |
| anggaran, RAPB | `budget`, `budget_plan` |
| yayasan | `foundation` |
| prodi, mahasiswa, NIM | `study_program`, `student`, `student_number` |
| tahun akademik/semester | `academic_term` |

## Uang dan waktu

- Rupiah utuh sebagai `int64`. Pembulatan lewat satu fungsi bersama dengan kebijakan eksplisit.
- Semua timestamp UTC di penyimpanan. Tanggal bisnis (jatuh tempo, periode) dalam zona Asia/Jakarta (WIB). Tahun fiskal dan periode akuntansi dapat dikonfigurasi per entity.

## Tarif dan tagihan

- Tarif berversi (`effective_from`). Tagihan menyimpan referensi versi tarif dan snapshot nilainya.
- **Tagihan yang sudah terbit tidak dimutasi.** Perubahan = `void` lalu terbit ulang (reissue), dengan jejak audit.
- State machine invoice: `draft → issued → partially_paid → paid`; `issued|partially_paid → void`; `paid → refunded`. Transisi divalidasi di satu fungsi.
- Denda dihitung deterministik dari `due_date` dan versi kebijakan. Hasilnya dapat direproduksi.
- Tagihan berbasis SKS mengikuti KRS. Revisi KRS memicu reissue terkontrol, bukan edit tagihan lama.

## Pembayaran

- Kebijakan VA (statis per mahasiswa vs dinamis per tagihan) ditentukan konfigurasi provider. Kode tidak boleh mengasumsikan salah satunya.
- Alur webhook: verifikasi signature → simpan payload mentah ke `payment.inbox` (`UNIQUE (provider, provider_ref)`) → balas cepat → proses asinkron → efek ke ledger tepat satu kali.
- Cocokkan nominal, nomor VA, dan referensi dengan tagihan. Tidak cocok → karantina ke exception queue, **bukan** auto-apply.
- Kasus wajib ditangani: parsial, lebih bayar (jadi deposit), kurang bayar, duplikat, out-of-order, settlement lewat cut-off, reversal bank, pembayaran ke tagihan yang sudah void.
- Alokasi ke beberapa tagihan memakai urutan deterministik (FIFO jatuh tempo, atau prioritas komponen yang dikonfigurasi). Hasil alokasi disimpan eksplisit (`payment_allocations`).
- Rekonsiliasi harian: settlement provider/rekening koran vs ledger. Selisih masuk exception queue dengan pemilik dan SLA.
- Refund, pembatalan, dan penghapusan piutang: maker-checker.

## Badan hukum dan unit organisasi PTS

- entity_id adalah badan hukum yang memiliki/melaporkan aset dan kewajiban, bukan ID fakultas atau cost center.
- Universitas, kampus, fakultas, prodi, biro, program, dan unit usaha menjadi dimensi organisasi/cost center kecuali dokumen hukum menyatakan unit tersebut badan hukum terpisah.
- Pisahkan tahun buku (fiscal_year) dari tahun akademik/semester (academic_term).
- Dana terikat memiliki sumber, tujuan, periode, syarat penggunaan, dan saldo rekonsiliasi. Transfer antar-unit dalam satu badan hukum bukan otomatis pendapatan/beban baru badan hukum.
- Baca docs/workflows/pts-financial-workflows.md sebelum mengubah workflow transaksi PTS.

## Ledger dan jurnal otomatis

- Double-entry. Setiap jurnal seimbang, bertanggal bisnis, merujuk dokumen sumber (`source_type`, `source_id`), dan idempotent berdasarkan kunci sumber.
- Pola default (konfirmasikan dengan akuntan/auditor yayasan sebelum finalisasi COA):
  - Terbit tagihan: Dr Piutang Mahasiswa / Cr Pendapatan Diterima di Muka.
  - Pembayaran diterima: Dr Kas/Bank (atau Rekening VA) / Cr Piutang Mahasiswa.
  - Pengakuan pendapatan per periode: Dr Pendapatan Diterima di Muka / Cr Pendapatan SPP/UKT.
  - Beasiswa/potongan: Dr Beban Beasiswa (atau Potongan) / Cr Piutang Mahasiswa.
- Pelaporan menggunakan ReportProfile yang disetujui badan hukum. Pertimbangkan SAK EP bila memenuhi kriteria, atau SAK Indonesia dengan ISAK 335 untuk entitas berorientasi nonlaba bila kerangka tersebut dipilih. Jangan menganggap satu standar otomatis berlaku bagi semua PTS. Catat versi dan tanggal efektif standar pada profil. Dana dengan/tanpa pembatasan direpresentasikan melalui akun dan dimensi funding restriction sesuai standar/kebijakan.
- Period closing: periode tertutup tidak menerima posting. Koreksi lewat jurnal pembalik di periode terbuka.

## Pelaporan PTS

- Pisahkan laporan manajemen universitas (RKAT, komitmen, realisasi, kas, pendapatan, piutang, SPJ) dari laporan keuangan badan hukum.
- Untuk yayasan, periksa paket laporan tahunan menurut UU Yayasan yang berlaku: posisi keuangan, aktivitas, arus kas, catatan, tanda tangan Pengurus/Pengawas, dan pengesahan Pembina sesuai ketentuan.
- Laporan yang disahkan disimpan sebagai snapshot immutable dengan standar, periode, mapping COA, filter, timestamp, preparer/reviewer/approver, dan sumber data.
- Baca docs/reporting/pts-financial-report-templates.md sebelum membuat laporan resmi atau ekspor.

## Pajak dan payroll

- PPh 21 (skema TER), PPh 23, PPh 4(2), PPN: tarif, PTKP, dan tabel TER disimpan sebagai data berversi dengan `effective_from`. Tidak ada angka pajak hardcode di kode.
- Ekspor ke Coretax dibuat sebagai adapter terpisah. Format dan kewajiban mengikuti aturan DJP terkini; verifikasi sebelum implementasi.
- Payroll mengonsumsi master pegawai dari SIMPEG (read model lokal). Honor per SKS mengacu data akademik yang sudah final.

## Anggaran dan pengeluaran

- Budget check dilakukan saat pengajuan dana dan pada approval. Penyerapan dicatat sebagai komitmen lalu realisasi.
- Approval berjenjang dikonfigurasi per unit/nominal. Pembuat tidak boleh menjadi penyetuju (ditegakkan di service dan DB).
