import type { Answer, Result } from './types';

export const scenarios = [
  { id: 'paket', title: 'Paket tertahan?', description: 'Pesan kurir dengan permintaan biaya', icon: 'package', message: 'Paket Anda tertahan. Transfer biaya pengiriman ulang Rp15.000 sekarang dalam 10 menit agar tidak dikembalikan. Jangan hubungi kantor, cukup balas pesan ini.' },
  { id: 'edukasi', title: 'Pengingat dari keluarga', description: 'Pesan edukasi tentang kode OTP', icon: 'messages-square', message: 'Bu, jangan pernah berikan kode OTP atau PIN ke siapa pun, termasuk yang mengaku petugas bank. Kalau ada yang menelepon, tutup lalu hubungi nomor resmi bank.' },
  { id: 'suara', title: 'Suara yang terdengar akrab', description: 'Transkrip panggilan meminta transfer', icon: 'audio-lines', message: 'Ini aku, Bu. Tolong transfer sekarang, aku lagi darurat. Jangan telepon balik dulu dan jangan bilang siapa-siapa.' },
];

const base: Omit<Result, 'case_id' | 'risk' | 'summary' | 'evidence'> = {
  mode: 'simulation', created_at: '2026-10-15T00:00:00Z', revision: 1, models: { demo: 'Skenario sintetis v1 · tanpa inferensi model' },
  checks: [], limitations: ['Ini skenario buatan untuk mencoba alur Sinyara. Tidak ada model AI yang dijalankan.', 'Hasil ini tidak menilai pesan, tautan, atau rekaman milik pengguna.'],
  next_steps: ['Tunda tindakan dan konfirmasi melalui kanal resmi yang kamu cari sendiri.', 'Jangan bagikan OTP, PIN, atau kata sandi.', 'Ajak keluarga atau orang tepercaya memeriksa situasinya.'],
};

export function fixture(id: string): Result {
  const scenario = scenarios.find(s => s.id === id) ?? scenarios[0];
  if (id === 'edukasi') return {
    ...structuredClone(base), case_id: `contoh-${id}`, risk: 'low',
    summary: 'Pesan ini berisi pengingat untuk menjaga kode rahasia. Belum ditemukan indikator kuat pada skenario ini.',
    evidence: [{ id: 'e1', source: 'message', quote: 'jangan pernah berikan kode OTP atau PIN ke siapa pun', indicator: 'protective_context', explanation: 'Kata OTP muncul sebagai larangan membagikan data, bukan permintaan kode.' }, { id: 'e2', source: 'message', quote: 'hubungi nomor resmi bank', indicator: 'protective_context', explanation: 'Pesan mendorong verifikasi secara mandiri melalui jalur resmi.' }],
    checks: [{ key: 'content', title: 'Isi dan konteks', status: 'done', detail: 'Contoh: konteks edukasi dan negasi diperhitungkan.' }, { key: 'reputation', title: 'Reputasi tautan', status: 'skipped', detail: 'Tidak ada tautan dalam skenario.' }, { key: 'forensic', title: 'Indikasi suara sintetis', status: 'skipped', detail: 'Tidak ada rekaman dalam skenario.' }],
  };
  if (id === 'suara') return {
    ...structuredClone(base), case_id: `contoh-${id}`, risk: 'high',
    summary: 'Permintaan transfer disertai larangan menelepon balik dan merahasiakan percakapan perlu segera diverifikasi.',
    evidence: [{ id: 'e1', source: 'audio', quote: 'Tolong transfer sekarang, aku lagi darurat.', indicator: 'payment_request', explanation: 'Permintaan pembayaran disertai tekanan keadaan darurat.', start: 2, end: 6 }, { id: 'e2', source: 'audio', quote: 'Jangan telepon balik dulu dan jangan bilang siapa-siapa.', indicator: 'secrecy', explanation: 'Permintaan ini membatasi kesempatan untuk memverifikasi identitas.', start: 6, end: 11 }],
    checks: [{ key: 'content', title: 'Isi percakapan', status: 'done', detail: 'Contoh analisis isi dari transkrip sintetis.' }, { key: 'transcription', title: 'Transkripsi suara', status: 'limited', detail: 'Hanya naskah contoh; rekaman audio tidak disertakan.' }, { key: 'forensic', title: 'Indikasi suara sintetis · eksperimental', status: 'inconclusive', detail: 'Belum dapat disimpulkan. Suara yang akrab tidak membuktikan identitas; suara sintetis juga tidak otomatis penipuan.' }],
    limitations: [...base.limitations, 'Timestamp adalah ilustrasi segmen. Tidak ada rekaman yang diputar dalam contoh ini.'],
  };
  return {
    ...structuredClone(base), case_id: `contoh-${id}`, risk: 'high',
    summary: 'Ada permintaan pembayaran yang disertai batas waktu singkat dan upaya menghindari verifikasi.',
    evidence: [{ id: 'e1', source: 'message', quote: 'Transfer biaya pengiriman ulang Rp15.000 sekarang dalam 10 menit', indicator: 'urgency', explanation: 'Permintaan uang disertai tenggat singkat dapat mendorong keputusan tanpa memeriksa.' }, { id: 'e2', source: 'message', quote: 'Jangan hubungi kantor, cukup balas pesan ini.', indicator: 'secrecy', explanation: 'Pengirim meminta penerima menghindari saluran verifikasi lain.' }],
    checks: [{ key: 'content', title: 'Isi dan konteks', status: 'done', detail: 'Contoh: permintaan uang, tekanan waktu, dan pembatasan verifikasi.' }, { key: 'reputation', title: 'Reputasi tautan', status: 'skipped', detail: 'Tidak ada tautan yang diperiksa.' }, { key: 'forensic', title: 'Indikasi suara sintetis', status: 'skipped', detail: 'Tidak ada rekaman yang diberikan.' }],
  };
}

export function fixtureAnswer(question: string, result: Result, remaining: number): Answer {
  const lower = question.toLowerCase();
  let answer = result.risk === 'low'
    ? 'Dalam skenario ini, pesan melarang membagikan OTP. Konteks larangan tersebut berbeda dengan permintaan kode rahasia. Ini tetap bukan jaminan keamanan pengirim. [e1]'
    : 'Dalam skenario ini, permintaan pembayaran disertai tekanan untuk segera bertindak. Tunda transaksi, lalu hubungi pihak terkait lewat nomor resmi yang kamu cari sendiri. [e1]';
  if (/suara|asli|palsu|identitas/.test(lower)) answer = 'Keaslian suara dan identitas pembicara belum dapat disimpulkan. Contoh ini hanya memuat naskah buatan. Verifikasi lewat nomor yang sudah kamu kenal.';
  if (/lakukan|langkah|aman|balas/.test(lower)) answer = 'Jangan kirim uang atau data rahasia dulu. Konfirmasi lewat kanal resmi yang kamu cari sendiri; hindari memakai nomor atau tautan yang diberikan pengirim. Ini saran verifikasi untuk skenario contoh.';
  return { answer: `Contoh jawaban — simulasi. ${answer}`, evidence_ids: ['e1'], remaining, limited: true };
}
