# Format Laporan Keuangan dan Template SIMKEU PTS

## 1. Dua jalur pelaporan

SIMKEU menyediakan dua kelompok laporan yang sumber datanya saling terhubung, tetapi tujuan dan formatnya berbeda.

A. **Laporan manajemen universitas** dipakai Rektor, WR, Kabiro, Kabag, dan unit untuk mengelola kegiatan, anggaran, dan arus kas. Formatnya mengikuti RKAT/SOP internal PTS.

B. **Laporan keuangan badan hukum penyelenggara** dipakai Pengurus, Pengawas, Pembina, auditor, dan pengguna eksternal sesuai kewajiban badan hukum. Paket final mengikuti standar akuntansi yang dipilih badan hukum dan ketentuan yang berlaku.

Jangan menerbitkan laporan manajemen unit seolah-olah merupakan laporan keuangan resmi badan hukum. Header menyatakan apakah laporan bersifat internal, konsolidasi, unaudited, audited, atau telah disahkan.

## 2. Standar pelaporan: profil yang dapat dipilih

Jangan hardcode satu standar hanya karena institusi adalah PTS atau penyelenggaranya yayasan.

Simpan ReportProfile dengan badan hukum pelapor, bentuk hukum, standar yang dipilih, tanggal efektif, versi standar, basis akuntansi, kebijakan pengakuan, mapping COA, kategori aset neto/pembatasan dana, format komparatif, dan aturan sign-off.

Pilihan yang perlu dievaluasi dengan akuntan/auditor:

1. **SAK Indonesia untuk Entitas Privat (SAK EP)** apabila badan hukum memenuhi kriteria penggunaannya, secara umum entitas tanpa akuntabilitas publik yang menerbitkan laporan keuangan tujuan umum. SAK EP efektif 1 Januari 2025. Topiknya mencakup penyajian laporan posisi keuangan, penghasilan komprehensif/laba rugi, perubahan ekuitas atau saldo laba, arus kas, dan catatan atas laporan keuangan.
2. **SAK Indonesia untuk entitas berorientasi nonlaba**: gunakan ISAK 335 (penomoran saat ini; sebelumnya dikenal sebagai ISAK 35) bersama standar SAK Indonesia yang relevan, jika kerangka ini dipilih badan hukum. IAI mengesahkan amendemen ISAK 335 pada 3 Juni 2026 untuk menyelaraskan panduan dengan PSAK 118. PSAK 118 dijadwalkan efektif 1 Januari 2027. Tanggal efektif/transisi amendemen ISAK 335 harus diperiksa pada publikasi resmi SAK Online sebelum konfigurasi production.
3. Standar lain hanya bila bentuk/akuntabilitas badan hukum dan regulasi memang mensyaratkan atau mengizinkannya.

Pemilihan standar tidak dilakukan AI atau developer. Persetujuan tertulis harus berasal dari pengurus badan hukum bersama akuntan/auditor.

## 3. Paket laporan manajemen PTS

| Kode | Nama laporan | Isi minimum | Pengguna |
|---|---|---|---|
| MGT-01 | Ringkasan eksekutif | Pendapatan, beban, kas, bank, piutang, komitmen, realisasi RKAT, risiko | Rektor, WR |
| MGT-02 | Realisasi RKAT | Pagu, revisi, komitmen, realisasi, sisa pagu, variance, persentase | Rektor, WR, Kabiro, Kabag |
| MGT-03 | Pendapatan | SPP/biaya pendidikan, registrasi, wisuda, layanan, hibah, unit usaha; target vs realisasi | Rektor, WR, Pendapatan |
| MGT-04 | Piutang dan aging | Tagihan, pembayaran parsial, saldo, umur piutang, beasiswa/dispensasi, exception | Kabiro, Kabag, Pendapatan |
| MGT-05 | Pengeluaran per unit | Anggaran, komitmen, beban aktual, kas keluar, vendor, program, SPJ | Kabiro, Kabag |
| MGT-06 | Kas dan bank | Saldo buku, saldo bank, outstanding, hasil rekonsiliasi, mutasi | Kabiro, Bendahara |
| MGT-07 | Pengajuan dan approval | Antrean, nilai, umur, posisi approval, SLA, alasan retur | Rektor, WR, Kabiro |
| MGT-08 | SPJ dan uang muka | Uang muka, SPJ jatuh tempo, belum lengkap, retur, nilai belum dipertanggungjawabkan | Kabiro, Kabag, Verifikasi |
| MGT-09 | Dana terikat/hibah/beasiswa | Sumber dana, saldo tersedia, tujuan, realisasi eligible, saldo belum digunakan | Kabiro, Kabag |
| MGT-10 | Payroll dan honorarium | Komponen biaya dan unit; akses sangat terbatas, ringkasan agregat untuk pimpinan | Kabiro |
| MGT-11 | Belanja modal dan aset tetap | Pengadaan, kapitalisasi, lokasi, mutasi, penyusutan, pelepasan | Kabiro, Kabag |
| MGT-12 | Analisis multi-periode | Bulan, semester, tahun buku, tahun akademik, komparatif dan tren | Rektor, WR |

Definisi angka MGT-02:
- Pagu tersedia = pagu efektif setelah revisi.
- Komitmen = pengajuan/kontrak/PO yang disetujui dan belum dibatalkan/direalisasi.
- Realisasi akuntansi = transaksi yang diakui sesuai basis akrual/kebijakan.
- Kas keluar = pembayaran yang telah settlement.
- Sisa pagu operasional = pagu efektif dikurangi komitmen yang masih berlaku dan realisasi yang belum terwakili dalam komitmen.
- Tampilkan realisasi akrual dan kas secara terpisah.

## 4. Paket laporan badan hukum/yayasan

Untuk badan penyelenggara berbentuk yayasan, UU Yayasan mengatur laporan tahunan tertulis paling lambat 5 bulan setelah tahun buku ditutup. Laporan tahunan mencakup keadaan/kegiatan yayasan dan laporan keuangan berupa laporan posisi keuangan akhir periode, laporan aktivitas, laporan arus kas, dan catatan laporan keuangan. Laporan ditandatangani Pengurus dan Pengawas sesuai Anggaran Dasar dan disahkan rapat Pembina.

Ikhtisar laporan tahunan diumumkan pada papan pengumuman kantor yayasan. Berdasarkan Pasal 52 UU 16/2001 sebagaimana diubah UU 28/2004, kewajiban pengumuman di surat kabar harian dan audit Akuntan Publik berlaku jika yayasan menerima bantuan negara/luar negeri/pihak lain minimal Rp500 juta dalam satu tahun buku atau memiliki kekayaan di luar harta wakaf minimal Rp20 miliar. Periksa ketentuan aktual dan keadaan badan hukum sebelum menandai kewajiban audit/publikasi sebagai berlaku.

Template tahunan:
1. Sampul dan identitas badan hukum.
2. Laporan keadaan dan kegiatan yayasan.
3. Laporan posisi keuangan.
4. Laporan aktivitas/kinerja keuangan.
5. Laporan arus kas.
6. Catatan atas laporan keuangan: kebijakan, rincian akun, pihak berelasi, komitmen/kontinjensi, pembatasan dana, aset, kewajiban, dan kejadian setelah periode.
7. Lampiran laporan unit/institusi dan rekonsiliasi bila dibutuhkan.
8. Pernyataan Pengurus/Pengawas, tanda tangan, dan pengesahan Pembina sesuai AD/ART.
9. Laporan auditor independen bila diwajibkan atau ditetapkan badan hukum.

## 5. Struktur template laporan

Header:
- Logo resmi dan nama badan hukum.
- Nama institusi/universitas bila laporan unit.
- Nomor dokumen dan versi.
- Nama laporan.
- Periode dan tanggal cut-off.
- Status Draft / Reviewed / Approved / Audited.
- Unit dan filter yang digunakan.

Tabel:
- Kode akun / kode program.
- Nama akun / uraian.
- Periode berjalan dan periode komparatif.
- Anggaran dan realisasi untuk laporan manajemen.
- Komitmen dan sisa pagu untuk laporan manajemen.
- Catatan/rujukan dokumen untuk rincian material.

Penutup:
- Disusun oleh.
- Diperiksa oleh.
- Disetujui/disahkan oleh sesuai kewenangan.
- Tanggal tanda tangan.
- Nomor halaman dan waktu ekspor.
- ID snapshot laporan agar file dapat ditelusuri ke data dan parameter yang sama.

## 6. Aturan keterbacaan dan format

### PDF
- A4 portrait untuk ringkasan/laporan posisi; landscape untuk tabel lebar.
- Kop dan judul jelas; header tabel berulang di setiap halaman.
- Subtotal/total dibedakan dengan garis dan hierarki tipografi, bukan warna saja.
- Angka rata kanan, kode rata kiri, uraian tidak terpotong.
- Footer memuat nomor halaman, waktu ekspor, report snapshot ID.
- PDF berupa teks yang dapat dicari, bukan gambar screenshot.

### XLSX
- Satu sheet ringkasan dan sheet detail terpisah.
- Freeze panes, autofilter, lebar kolom wajar, format Rupiah, tanggal konsisten.
- Nilai angka berupa numeric cells; formula subtotal/total dapat diaudit.
- Header tabel, print area, orientasi, repeated print rows, dan metadata laporan ditetapkan.
- Proteksi sheet bukan pengganti otorisasi sistem.

### XLS lama
- Disediakan hanya untuk kompatibilitas lama.
- XLS dapat memiliki batas format/kapasitas lebih rendah daripada XLSX.
- Jika library XLS belum dipilih dan diuji, jangan tampilkan tombol ekspor XLS seolah sudah tersedia.

## 7. Impor data keuangan

Pola staging:
1. Upload ke penyimpanan privat; validasi magic bytes, ukuran, malware scan, dan hak akses.
2. Parse ke staging table, bukan langsung ke transaksi posted.
3. Tampilkan preview, mapping kolom, jumlah baris, total nominal, dan kesalahan per baris.
4. Validasi kode akun, unit, periode terbuka, sumber dana, duplikasi, dan total kontrol.
5. Maker submit; verifier/approver berbeda menyetujui bila impor berdampak finansial.
6. Setelah disetujui, service domain membuat dokumen transaksi dan memanggil ledger.post secara idempotent.
7. Simpan checksum, source ID, import batch ID, hasil validasi, user, dan audit trail.

Template impor mencantumkan versi template dan schema version. Jangan mengimpor formula Excel sebagai nilai tepercaya; hitung ulang total di server.

## 8. Validasi laporan

Sebelum final export:
- Trial balance: total debit = total kredit.
- Rekonsiliasi bank dan kas selesai atau exception diberi pengungkapan.
- Piutang, utang, uang muka, dan komitmen direkonsiliasi.
- Mapping COA ke laporan lengkap; tidak ada akun unmapped.
- Dana terikat direkonsiliasi per donor/sumber/tujuan.
- Periode dan cut-off benar.
- Angka komparatif dan satuan mata uang konsisten.
- Status laporan dan paraf sesuai matriks sign-off.

Simpan laporan yang disahkan sebagai snapshot immutable. Revisi laporan membuat versi baru, bukan menimpa file resmi sebelumnya.
