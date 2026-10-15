# Evaluasi dan batas klaim

Catatan awal 15 Oktober 2026. Pisahkan keberhasilan perangkat lunak dari akurasi model dan kegunaan produk. Hasil di sini dapat direproduksi dari skrip dan artifact JSON; tidak ada data pengguna yang dipakai.

## Pemeriksaan perangkat lunak

Pengujian pytest meliputi domain utama/userinfo/IDN, URL yang dilarang, tidak adanya panggilan DNS, sumber reputasi yang belum tersedia, isolasi token antarkasus, penghapusan saat pekerjaan berjalan, TTL tanpa perpanjangan oleh polling, kuota, antrean penuh, format/ukuran input, audio rusak/terlalu panjang/senyap, salinan ASR dan forensik yang terpisah, model tidak tersedia, referensi palsu, serta kontrak FastAPI/Gradio.

Run lokal terakhir mencakup 35 tes Python. Pemeriksaan UI meliputi delapan tes, termasuk pembatalan polling yang tidak boleh menampilkan hasil kasus sebelumnya dan fokus tombol pembatalan yang tetap bertahan saat progres diperbarui.

Vitest/jsdom memeriksa escaping HTML, penyamaran ekspor, validasi input, formulir yang mempertahankan isi lintas tab, keyboard tab, tidak munculnya verdict input pribadi di mode simulasi, hasil contoh dan percakapan yang konsisten berlabel simulasi. CI memakai pengganti model agar tidak perlu jaringan model atau GPU.

Browser diperiksa pada 390 px dan 1280 px. Overflow horizontal ponsel dari dekorasi diperbaiki; snapshot DOM sesudah perbaikan menunjukkan halaman tidak melebihi viewport. Screenshot ponsel ada di `docs/images`. Dukungan reduced motion dinyatakan melalui CSS dan juga perlu diperiksa dengan pengaturan OS/browser pengguna. Pengujian pembaca layar khusus dan uji pengguna keluarga belum dilakukan.

## Regresi model bahasa lokal

Baseline: Ollama `qwen3:4b`, CPU/iGPU laptop Windows dengan RAM sekitar 16 GB. Jalankan:

```bash
uv run --extra eval python scripts/benchmark.py --output artifacts/benchmark-qwen3.json --mlflow
```

Dataset `eval/messages.jsonl` berisi **8 pesan sintetis yang dibuat untuk pengembangan**: empat dengan permintaan berisiko dan empat pesan sah/edukasi/negasi. Risiko positif didefinisikan sebagai label `high` atau `verify`; `insufficient` dihitung sebagai abstention yang gagal menemukan kasus positif untuk recall.

| Metrik | Baseline setelah perbaikan skema |
| --- | --- |
| Label tepat | 8 / 8 |
| Pemeriksaan isi selesai | 8 / 8 |
| Precision pada 8 contoh | 1,00 |
| Recall pada 8 contoh | 1,00 |
| False positive pada 4 contoh sah | 0 / 4 |
| Median waktu respons | 17,21 detik |

Artifact: [`benchmark-qwen3.json`](../artifacts/benchmark-qwen3.json). Durasi dapat berubah karena cold start, beban aplikasi lain, dan konfigurasi model. Angka tersebut **bukan estimasi akurasi pada masyarakat umum**. Tidak ada interval keyakinan yang memadai, holdout independen, atau uji dialek dalam set kecil ini.

Kandidat Ollama `qwen3.5:4b` juga menyelesaikan 8/8 label pada set yang sama, dengan median 32,52 detik. Artifact: [`benchmark-qwen35.json`](../artifacts/benchmark-qwen35.json). Konfigurasi lokal tetap memilih baseline Qwen3 4B karena lebih cepat pada perangkat ini. Perbandingan bukan percobaan latency terkontrol dan tidak menjamin urutan yang sama pada GPU atau beban berbeda.

Eksperimen awal tersimpan di [`benchmark-local.json`](../artifacts/benchmark-local.json): ID sumber sempat diisi dengan isi pesan, sehingga validasi menolak sebagian besar hasil. Dynamic enum ID dan contoh format dalam prompt memperbaiki masalah tersebut. Dua contoh pengembangan diverifikasi sebelum menjalankan ulang delapan pesan. Karena perubahan dibuat berdasarkan set yang sama, hasil ini harus diperlakukan sebagai regresi pengembangan, bukan holdout.

`memory_rss_bytes` mengukur RSS proses pipeline Python saat sample selesai. Nilai ini **tidak mencakup proses Ollama, model di GPU, atau peak memory antar-sample**. Jangan menggunakannya sebagai total kebutuhan RAM sistem.

## Transkripsi dan suara sintetis

`scripts/smoke_audio.py` menjalankan Whisper small INT8 dan AASIST pada satu detik near-silence buatan, seed 42. Whisper tidak menghasilkan segmen; AASIST berhasil menghasilkan skor mentah dan tetap `inconclusive`. Artifact: [`audio-smoke.json`](../artifacts/audio-smoke.json). Ini memverifikasi pemuatan/inferensi, bukan WER atau EER.

`scripts/evaluate_fleurs_sample.py` menyediakan uji integrasi pada **satu rekaman Indonesia publik** dari [Google FLEURS](https://huggingface.co/datasets/google/fleurs), lisensi CC BY 4.0, dengan atribusi pada artifact. Variannya: WAV asli, noise deterministik 10 dB, dan MP3 64 kbps. Script mengambil satu WAV secara streaming, tidak menyimpan audio dalam Git. Jika artifact dihasilkan, hasilnya tetap hanya uji satu speaker/kalimat, bukan benchmark bahasa Indonesia secara umum.

Run awal menghasilkan WER 0,00 pada WAV, 0,067 pada versi noise 10 dB, dan 0,00 pada MP3. Lihat [`fleurs-sample-smoke.json`](../artifacts/fleurs-sample-smoke.json) untuk teks referensi, transkripsi, timestamp, hash sumber, dan durasi. Ketiga angka berasal dari rekaman yang sama sehingga tidak boleh dianggap tiga sampel independen.

Uji chat di browser menemukan klaim keabsahan domain yang berlebihan meskipun ID referensinya cocok. Guard domain dan pemeriksaan dukungan klaim oleh model ditambahkan dengan regression test. Pemeriksaan model terhadap jawabannya sendiri tetap bukan jaminan kebenaran; review manusia masih diperlukan.

Sesudah perbaikan, [`followup-smoke.json`](../artifacts/followup-smoke.json) memuat jawaban nyata yang diterima pemeriksa bukti: pertanyaan gabungan pesan/URL serta pertanyaan sesudah konteks baru. Referensi menunjuk bukti yang tersedia, reputasi dinyatakan belum diperiksa, dan revisi kasus naik menjadi 2. Waktu pada run tersebut sekitar 43 detik untuk pertanyaan pertama dan 46 detik untuk konteks beserta peninjauan ulang. Ini mencakup pemeriksaan dukungan oleh model, sehingga lebih lama daripada analisis pertama.

SDK JavaScript `@gradio/client` juga diuji terhadap Gradio lokal: buat kasus, tiga snapshot stream, hasil `mode=real`, lalu penghapusan. Konfigurasi runtime mengonfirmasi `run_history=false`. Penutupan koneksi SDK saat smoke test dapat mencetak diagnostik AbortError dari pembatalan stream; operasi kontrak sendiri berhasil. Uji ini tidak memverifikasi alokasi GPU atau kuota di Hugging Face.

Evaluasi forensik manusia/sintetis Indonesia yang memadai **belum tersedia**. Oleh sebab itu:

- Tidak ada klaim EER Indonesia atau akurasi deepfake publik.
- Skor AASIST tidak diubah menjadi probabilitas atau persentase.
- Tidak ada threshold diaktifkan pada produk.
- Inferensi forensik tidak mengubah penilaian risiko isi percakapan.

## Protokol evaluasi selanjutnya

Gunakan rekaman yang pemakaiannya diizinkan dan dokumentasikan sumber, lisensi/persetujuan, bahasa/dialek, codec, kualitas, speaker, serta generator. Mulai dari `eval/audio_manifest.example.csv`. Manifest lengkap berisi `path,split,label,speaker_id,generator_id,origin_id,codec,reference,consent`.

Pisahkan speaker, generator sintetis, dan sumber rekaman antara development dan test. Semua varian kompresi dari satu rekaman tetap pada split yang sama. `evaluate_audio.py` menolak kebocoran ID dan mewajibkan contoh manusia/sintetis di kedua split serta audio terkompresi di test.

Pilih threshold hanya dari dev set. Ukur FAR/FRR pada holdout dengan threshold tersebut dan laporkan EER terpisah. Implementasi skrip memakai nearest empirical crossing, bukan interpolasi evaluator ASVspoof resmi. Jumlah sampel, interval ketidakpastian, kondisi codec, variasi dialek, dan kegagalan perlu dilaporkan sebelum mengaktifkan threshold.

Untuk pesan, kumpulkan sampel sah yang mendesak, edukasi, negasi, penipuan yang halus, code switching, keluarga, kurir, bank, lowongan, dan investasi. Pisahkan sumber/template antara dev dan holdout. Pakai dua anotator dan adjudikasi untuk label yang berbeda. Laporkan precision/recall, false positive, abstention/coverage, label per kategori, latency p50/p95, dan konsumsi memori proses model secara terpisah.

Untuk percakapan, tinjau setiap klaim terhadap bukti, bukan hanya keberadaan citation ID. `eval/evidence_review.example.csv` menyediakan kolom review. Nilai juga apakah tambahan konteks memperbaiki hasil atau justru menuruti klaim pengguna tanpa verifikasi.

Belum ada benchmark Qwen3.5 Transformers pada ZeroGPU atau Qwen-ASR di akun pengguna. Integrasi ini baru boleh disebut terverifikasi sesudah berjalan pada host target. IndoBERT tetap rencana baseline fine-tuning, tidak diklaim sebagai classifier penipuan siap pakai.
