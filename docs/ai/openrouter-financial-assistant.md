# AI Financial Assistant SIMKEU — OpenRouter

## Tujuan

AI membantu pengguna memahami laporan dan menyiapkan draft narasi keuangan. AI bukan engine akuntansi, approver, bendahara, atau pengganti auditor.

## Arsitektur request

~~~text
User question
  → SIMKEU authentication
  → service authorization (role + legal entity + unit scope)
  → report/query service (approved query catalog)
  → aggregated, minimized result + source metadata
  → OpenRouter gateway
  → schema-validated response
  → user review / approval
  → audit record
~~~

OpenRouter tidak menerima database credential dan tidak boleh menjalankan SQL bebas. Semua angka dihitung oleh service/reporting query yang deterministik.

## Environment

~~~dotenv
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
OPENROUTER_SITE_URL=
OPENROUTER_APP_NAME=SIMKEU
OPENROUTER_TIMEOUT_SECONDS=30
OPENROUTER_MAX_OUTPUT_TOKENS=2500
~~~

Gunakan API server-side OpenRouter Chat Completions di https://openrouter.ai/api/v1/chat/completions. Model diatur melalui konfigurasi, bukan hardcode di frontend. API key hanya tersedia pada server/secret manager.

## Use cases

- Ringkasan realisasi RKAT per badan hukum/unit/periode.
- Penjelasan variance anggaran, komitmen, aktual akrual, dan kas keluar.
- Ringkasan tren pendapatan, piutang, pengeluaran, kas/bank.
- Draft narasi untuk laporan Rektor/WR dan laporan tahunan badan penyelenggara.
- Klasifikasi awal dokumen sebagai saran untuk verifikator; keputusan akhir tetap manusia.
- Natural-language query yang dipetakan ke katalog laporan yang diizinkan.

## Contract untuk setiap jawaban angka

Sertakan legal_entity_id, institution_id atau organization_unit_id bila ada, report_code, period_start, period_end, as_of, filter, basis pelaporan, generated_at, source_snapshot_id, angka terstruktur dari backend, dan batasan data/exception yang belum selesai.

AI tidak boleh mengisi angka yang tidak tersedia. Bila field hilang, jawaban harus menyatakan tidak tersedia.

## Safety dan privasi

- Scope dihitung server berdasarkan user; jangan meminta LLM menentukan izin.
- Data pegawai, mahasiswa, rekening, pajak, kontrak, dan vendor diminimalkan/masking sebelum dikirim.
- Hanya data agregat yang diperlukan boleh dikirim ke model.
- Jangan mengirim dokumen pribadi mentah kecuali ada dasar, persetujuan, dan kebijakan retensi/pemrosesan yang disetujui.
- AI tidak boleh menyetujui pengajuan, menandatangani laporan, menjalankan refund, membuat pembayaran, menutup periode, atau menulis ledger.
- Semua output yang dipakai dalam dokumen resmi harus direview dan disetujui manusia.
- Catat provider/model, prompt version, source snapshot ID, penggunaan token, status review; jangan simpan secret/PII dalam log.

## Structured output

Gunakan schema response dengan field summary, key_findings, variance_explanations, risks, recommendations, source_references, limitations, dan requires_human_review. Validasi response di backend. Jika schema tidak valid atau sumber data kosong, jangan tampilkan rekomendasi seolah faktual.
