# Privasi, akses, dan batas keamanan

## Data pengguna

- Input pribadi tidak dianalisis oleh build simulasi. Memilih contoh tidak memakai atau mengunggah isi formulir pengguna.
- Dengan backend terhubung, pesan, URL, dan audio dikirim ke layanan yang dikonfigurasi. Jalur lokal mengirim permintaan bahasa hanya ke Ollama lokal. Jalur Space mengirim input ke Hugging Face; konfigurasi Qwen-ASR terpisah mengirim salinan audio juga ke Space ASR tersebut.
- Kasus, transkrip, konteks, dan rekaman disimpan di memori aplikasi. Tidak ada database kasus atau file audio pengguna yang dibuat oleh pipeline.
- Masa simpan 15 menit tidak aktif; pemeriksaan background/poll tidak memperpanjang. Waktu pembersihan worker idle maksimal sekitar 30 detik; setiap akses memeriksa TTL terlebih dahulu.
- Penghapusan membuang kasus dan pekerjaan yang menunggu. Panggilan model yang sudah berjalan tidak selalu bisa dibatalkan seketika, tetapi hasilnya tidak disimpan kembali dan salinan kerjanya dilepas setelah selesai.
- Muat ulang/tutup tab membuang token dan state formulir browser. Itu tidak otomatis menghapus kasus di server; gunakan Hapus kasus atau tunggu TTL. Audio object URL dicabut ketika dilepas atau kasus dihapus dari UI.
- Metadata kuota sesi disimpan hingga 24 jam dalam memori. Log aplikasi hanya seharusnya memuat status, jenis error, durasi, dan metadata operasional; jangan menyalakan tracing request body di proxy.
- Run history Gradio dimatikan di server (`run_history=False`) dan klien browser (`record_history:false`) agar input/output tidak otomatis masuk riwayat local storage/bucket Gradio.
- Ekspor berupa teks yang menyamarkan pola nomor, email, tautan, dan kode yang tampak. Penyamaran bersifat upaya terbaik dan tidak menjamin semua nama atau detail sensitif terhapus. Periksa sebelum membagikan.

## Akses dan permukaan serangan

Token acak per kasus diperlukan untuk membaca, bertanya, menganalisis, dan menghapus. Token dibandingkan memakai constant-time comparison. Token tidak dimasukkan ke URL. Kasus tidak dapat dienumerasi dari pesan error; token salah dan kasus hilang sama-sama memberikan 404.

URL input diperlakukan sebagai data. Tidak ada DNS lookup, kunjungan halaman, perluasan shortlink, atau eksekusi unduhan. Public Suffix List memakai snapshot paket lokal sehingga proses analisis tidak melakukan refresh jaringan tersembunyi. Ini juga berarti snapshot bisa tertinggal dari perubahan domain terbaru.

Model tidak diberi tool yang dapat mengakses komputer atau jaringan. Instruksi di pesan tidak mendapat peran sistem. Output HTML di-escape sebelum dirender. Referensi ID dan kutipan diperiksa, tetapi prompt injection dan halusinasi tetap perlu dievaluasi pada korpus yang lebih besar.

Decoder memverifikasi byte audio dan membatasi durasi ketika decode. Ukuran body HTTP dibatasi, termasuk chunked request. Kasus/unggahan aktif dibatasi jumlah dan ukuran total. Decoder pihak ketiga tetap merupakan dependency yang perlu diperbarui. Untuk layanan publik dengan lalu lintas tinggi, pisahkan decoding dalam sandbox proses dengan batas waktu dan memori, serta tambahkan gateway rate limit.

## Yang belum disediakan

Kuota sesi dapat direset oleh pengguna dan bukan mekanisme anti-abuse yang kuat. Belum ada login, kontrol akun keluarga, verifikasi identitas, gateway IP limit, audit kepatuhan, atau SLA produksi. Jangan membuka API laptop ke internet dengan mengganti host menjadi `0.0.0.0` tanpa rancangan deployment yang sesuai.

Tidak ada jaminan penghapusan fisik memori OS, swap, crash dump, log provider, atau buffer framework. Gradio/provider dapat menahan buffer request/response sementara mengikuti kebijakannya. Data sensitif yang tidak diperlukan sebaiknya dihapus sebelum unggah. Model dan dataset latihan masing-masing mengikuti ketentuan sumbernya; unggahan tidak menjadi data latihan secara otomatis.
