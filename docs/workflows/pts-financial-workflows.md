# Workflow Keuangan SIMKEU PTS

Dokumen ini adalah workflow baseline. Rute final harus dikonfigurasi menurut Statuta, AD/ART, SOP keuangan, sumber dana, dan delegasi tertulis. Nama jabatan tidak otomatis menentukan limit persetujuan.

## 1. Siklus RKAT tahunan

~~~text
Unit pemilik anggaran menyusun usulan
    ↓
Kabag Keuangan: validasi format, pagu historis, kelengkapan
    ↓
Kabiro Keuangan & Umum: review lintas unit dan konsolidasi
    ↓
WR terkait: review prioritas program dan rencana strategis
    ↓
Rektor: review/rekomendasi/persetujuan sesuai delegasi
    ↓
Badan penyelenggara: persetujuan bila diwajibkan Statuta/AD/ART
    ↓
RKAT versi disahkan → pagu dibuka per unit dan sumber dana
~~~

Usulan berisi tujuan, output, indikator, jadwal, RAB, cost center, program, sumber dana, dan dokumen. Tampilkan pagu tahun sebelumnya, realisasi, komitmen, sisa, dan justifikasi perubahan. RKAT yang disahkan tidak diedit; revisi menghasilkan versi baru. Tahun buku keuangan terpisah dari tahun akademik/semester.

## 2. Revisi anggaran

~~~text
Unit mengajukan revisi + alasan + dokumen
    ↓
Sistem menghitung dampak pagu, komitmen, sumber dana
    ↓
Kabag memeriksa kode dan ketersediaan
    ↓
Kasubbag Verifikasi memeriksa bukti bila dipersyaratkan
    ↓
Kabiro review
    ↓
WR / Rektor / Badan Penyelenggara sesuai nilai dan jenis perubahan
    ↓
Versi anggaran baru aktif dengan effective date
~~~

Dana terikat tidak boleh dipindahkan ke tujuan lain tanpa otorisasi donor/perjanjian dan kebijakan berlaku. Revisi menyimpan alasan, akun asal/tujuan, unit, nominal, approver, waktu, dan versi RKAT.

## 3. Pengeluaran, pengadaan, dan pertanggungjawaban

~~~text
Pemohon/unit mengirim fund request
    ↓
Budget check: pagu tersedia? sumber dana sesuai? komitmen cukup?
    ↓
Kabag meninjau kebutuhan dan kode anggaran
    ↓
Kasubbag Verifikasi memeriksa dokumen, pajak, kontrak, kelengkapan
    ↓
Kabiro meninjau dan memberi rekomendasi
    ↓
WR / Rektor / Badan Penyelenggara sesuai delegasi
    ↓
Sistem membentuk komitmen anggaran
    ↓
Bendahara mengeksekusi pembayaran yang telah disetujui
    ↓
Bukti transfer + bukti transaksi tersimpan
    ↓
Unit menyerahkan SPJ
    ↓
Kasubbag Verifikasi memeriksa SPJ
    ↓
Kabag/Kabiro menutup kasus sesuai SOP
~~~

Aturan:
- Pengajuan memiliki pemohon, unit, tujuan, akun anggaran, program, sumber dana, nilai, jadwal, penerima/vendor, dan bukti.
- Budget check berjalan sebelum approval dan diperiksa kembali sebelum pembayaran.
- Approval menyimpan identitas, keputusan, waktu, komentar, delegasi, policy version.
- Bendahara hanya membayar instruksi berstatus approved dan lolos validasi rekening/penerima.
- Pemohon tidak memverifikasi SPJ sendiri. Bendahara tidak menjadi satu-satunya pihak yang menyetujui dan merekonsiliasi pembayaran yang dia eksekusi.
- SPJ memiliki due date, checklist, status, retur, batas revisi, dan exception queue.
- Pengakuan beban/utang/aset mengikuti basis akrual dan kebijakan; pembayaran kas bukan otomatis tanggal pengakuan beban.

## 4. Pendapatan dan penerimaan

~~~text
SIAKAD / kontrak / layanan / unit usaha mengirim sumber tagihan
    ↓
Bagian Pendapatan memeriksa master, tarif efektif, dispensasi, beasiswa
    ↓
Tagihan diterbitkan dengan nomor dan snapshot tarif
    ↓
Mahasiswa/pelanggan membayar via bank/VA/QRIS/teller
    ↓
Payment inbox memverifikasi signature/referensi/nominal
    ↓
Pendapatan mengalokasikan penerimaan dan menangani exception
    ↓
Bendahara/rekonsiliator memeriksa settlement terhadap rekening koran
    ↓
Ledger mem-posting jurnal melalui ledger.post
    ↓
Pendapatan dan Kabag memantau piutang serta selisih
~~~

Exception queue menangani nominal tidak cocok, pembayaran ganda/parsial/lebih/kurang, tagihan void, referensi tidak dikenal, settlement tidak masuk, reversal bank, dan transaksi lintas tanggal cut-off.

Tagihan yang sudah terbit tidak diubah diam-diam. Perubahan tarif/dispensasi menghasilkan dokumen koreksi atau reissue. Pengakuan pendapatan mengikuti periode layanan dan kebijakan akuntansi, bukan semata tanggal tagihan atau kas masuk.

## 5. Kas, bank, dan rekonsiliasi

- Bendahara merekam kas masuk/keluar dan bukti kas.
- Rekening koran diimpor ke staging, dinormalisasi, lalu dipadankan dengan transaksi sistem.
- Baris cocok diberi kandidat match; baris tidak cocok masuk queue investigasi.
- Rekonsiliasi final diperiksa pihak lain dengan permission terpisah.
- Selisih bank, transaksi menggantung, biaya bank, dan reversal memiliki reason code dan tindak lanjut.
- Saldo kas/bank dapat ditelusuri ke rekening, statement date, dan ledger.

## 6. Penutupan bulan/tahun

~~~text
Cut-off transaksi dan dokumen
  → Rekonsiliasi bank dan kas
  → Rekonsiliasi penerimaan, piutang, dan utang
  → Review komitmen dan SPJ belum selesai
  → Akrual, prepaid, pendapatan diterima di muka,
    penyusutan, persediaan, dan koreksi sesuai kebijakan
  → Trial balance dan review selisih
  → Kasubbag/Kabag menyiapkan checklist
  → Kabiro melakukan review
  → Maker-checker menutup periode
  → Reporting snapshot dibuat dan disahkan
~~~

Setelah ditutup, posting biasa ditolak. Koreksi dicatat sebagai jurnal pembalik/penyesuaian di periode terbuka. Membuka kembali periode memerlukan workflow khusus, otorisasi lebih tinggi, alasan, dan audit trail.

## 7. State machine minimum

| Dokumen | Status |
|---|---|
| RKAT | draft, submitted, review, approved, active, superseded, rejected |
| Revisi RKAT | draft, submitted, verified, approved, rejected, effective |
| Pengajuan dana | draft, submitted, budget_checked, verification, review, approval, approved, rejected, returned, cancelled |
| Pembayaran keluar | pending, authorized, processing, paid, failed, reversed |
| SPJ | not_due, pending, submitted, verification, returned, verified, closed, overdue |
| Tagihan | draft, issued, partially_paid, paid, void, refunded |
| Rekonsiliasi bank | imported, matching, exception, review, reconciled |
| Periode akuntansi | open, closing_review, closed |

Semua transisi melewati domain service dan memvalidasi permission, scope, limit, serta precondition. Tidak boleh ada update status langsung melalui endpoint CRUD generik.

## 8. Approval engine

Simpan definisi workflow sebagai data berversi:
- workflow_definition, workflow_version, workflow_step.
- approval_assignment dengan role/position dan scope unit.
- Kondisi: jenis dokumen, nominal, sumber dana, unit, kategori akun, pengecualian.
- approval_task: assigned user, decision, comment, timestamp, delegation.
- workflow_event: append-only state transition.

Workflow berjalan menggunakan snapshot aturan ketika pengajuan dibuat, kecuali kebijakan resmi menyatakan re-route. Pengajuan tidak boleh otomatis disetujui karena pejabat belum ditetapkan.
