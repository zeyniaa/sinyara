# Publikasi gratis dan backend AI

## Frontend

`npm run build` menghasilkan situs statis dalam `dist/`. `.env.production` menetapkan `VITE_BACKEND=simulation` agar file konfigurasi development tidak membuat demo publik mencoba mengakses localhost pengunjung.

Situs dapat dihosting melalui Sites atau host statis lain. `.openai/hosting.json` mengikat situs Sites untuk proyek ini. Jangan menyalin ID itu untuk membuat situs baru milik orang lain. Bila melakukan fork, hapus identitas deployment sebelum membuat situsmu sendiri.

Build bawaan tidak melakukan inferensi. Tiga contoh sintetis memperlihatkan seluruh alur; input pribadi diberi informasi backend belum terhubung. Font dan ikon masuk build; tidak perlu CDN font.

Untuk mengaktifkan backend yang sudah berhasil diuji, buat `.env.production.local` yang diabaikan Git:

```dotenv
VITE_BACKEND=gradio
VITE_SPACE=nama-akun/sinyara-api
```

Kemudian build dan deploy ulang. Jangan menaruh token Hugging Face rahasia dalam variabel `VITE_`; semua variabel tersebut menjadi bagian frontend publik. Template ditujukan untuk API publik berkuota tanpa secret di browser.

## Kelayakan ZeroGPU

Menurut [dokumentasi ZeroGPU](https://huggingface.co/docs/hub/en/spaces-zerogpu) yang diperiksa pada 15 Oktober 2026, akun gratis dengan email terverifikasi dan umur lebih dari 30 hari dapat memenuhi syarat menghosting hingga dua Gradio Space ZeroGPU. Provider menerapkan kuota waktu GPU per pengunjung dan antrean sendiri. Periksa ketentuan terbaru pada akun, jangan membeli resource berbayar hanya untuk mengikuti panduan ini.

Selama implementasi awal, tidak ada autentikasi Hugging Face yang tersedia di lingkungan pengguna. Umur akun dan verifikasi email tidak dapat dikonfirmasi. Karena itu, frontend simulasi dapat dipublikasikan, sedangkan aktivasi AI publik tetap menunggu akun/host yang memenuhi syarat. **Template berikut belum merupakan layanan GPU yang terverifikasi berjalan.**

## Mengapa dua lingkungan?

Paket resmi [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR/blob/main/pyproject.toml) mematok Transformers 4.57.6. Qwen3.5 menggunakan Transformers generasi lebih baru. Menginstal keduanya ke satu environment dengan `--no-deps` akan menyembunyikan konflik dan tidak menjadi konfigurasi yang didukung.

Template `deploy/main-space` memakai Transformers 5.x, sementara `deploy/asr-space` memakai dependensi resmi Qwen-ASR. Ini dapat memanfaatkan dua Space jika akun memang memenuhi syarat. Jika hanya satu Space tersedia, aktifkan pesan/URL dahulu dan laporkan transkripsi sebagai belum tersedia, atau gunakan Whisper CPU dengan cold start dan latensi yang perlu diuji.

## Menyiapkan Space

1. Pada akun yang sudah memenuhi syarat, buat Gradio Space dengan ZeroGPU; cek bahwa UI provider menunjukkan hardware gratis yang dimaksud.
2. Untuk **ASR**, salin `deploy/asr-space/{README.md,requirements.txt,app.py}` ke root Space. Tidak ada backend source lain yang diperlukan. Model dimuat saat startup; pengalokasian GPU hanya membungkus inferensi.
3. Untuk **API utama**, salin `deploy/main-space/{README.md,requirements.txt,app.py}` ke root Space, lalu salin `backend/` dari repositori Sinyara. Tetapkan environment `SINYARA_ASR_SPACE=nama-akun/sinyara-asr` dan `SINYARA_ASR_PROVIDER=qwen-remote` pada pengaturan Space.
4. AASIST opsional: jalankan setup resmi saat build untuk menyiapkan cache di Space, lalu set `SINYARA_AASIST_ENABLED=true` dan direktori yang benar. Bila tidak diaktifkan, UI harus tetap menyatakan bagian ini belum diperiksa. Skor tetap tidak boleh dipublikasikan sebagai probabilitas.
5. Matikan analytics yang tidak diperlukan. Jangan mengaktifkan log request/response body. Pastikan pengguna mengetahui jalur data ke dua Space.
6. Uji `createCase`, stream `analyzeCase`, `askFollowup` dengan konteks, dan `deleteCase` dari klien Gradio. Coba pengunjung anonim dan login terpisah untuk melihat efek kuota GPU provider.
7. Uji payload audio rusak/lebih dari 60 detik, antrean penuh, host sleep/restart, token silang, TTL, dan kegagalan salah satu Space. Jangan mengganti kegagalan dengan hasil simulasi yang tidak ditandai.
8. Setelah seluruh pemeriksaan host lulus, hubungkan `.env.production.local`, build frontend, lalu publish versi baru.

Runtime Gradio, versi PyTorch yang didukung, kebijakan ZeroGPU, dan dependency model dapat berubah. Gunakan lock yang sesuai host setelah integrasi terverifikasi. Versi PyTorch di laptop dapat berbeda dari host GPU. Template mematok 2.8.0 yang tercantum dalam rentang dukungan saat dokumentasi diperiksa.

## Batas sebelum peluncuran komersial

Masih diperlukan dataset Indonesia berizin, evaluasi lintas codec dan generator, threshold pada dev set dan holdout, rate limiting di gateway, pengujian beban dan decoder dalam proses terisolasi, tinjauan privasi sesuai tempat deployment, serta pemeriksaan merek/domain Sinyara.

Adapter reputasi sengaja belum aktif. Safe Browsing gratis dan VirusTotal public API memiliki batas nonkomersial; jangan menganggapnya otomatis cocok untuk bisnis. Periksa ketentuan produk yang dipilih sebelum menambah integrasi.
