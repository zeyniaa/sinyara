import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import '@fontsource/inter/latin-600.css';
import '@fontsource/inter/latin-700.css';
import './style.css';
import { createIcons, ArrowRight, ArrowUpRight, Plus, X, ShieldCheck, MessageSquareText, Link, AudioLines, Upload, LockKeyhole, ChevronDown, Check, CircleHelp, RotateCcw, Download, Trash2, Send, Play, Package, MessagesSquare, Sparkles, ArrowLeft, Info, CircleAlert, CheckCheck, ExternalLink } from 'lucide';
import { backend, client, ClientError } from './client';
import { fixture, fixtureAnswer, scenarios } from './fixtures';
import type { CaseAccess, CaseInput, Progress, Result, Risk } from './types';
import { escapeHtml as e, redact, timeLabel, validateForm } from './utils';

const icons = { ArrowRight, ArrowUpRight, Plus, X, ShieldCheck, MessageSquareText, Link, AudioLines, Upload, LockKeyhole, ChevronDown, Check, CircleHelp, RotateCcw, Download, Trash2, Send, Play, Package, MessagesSquare, Sparkles, ArrowLeft, Info, CircleAlert, CheckCheck, ExternalLink };
const icon = (name: string, cls = '') => `<i data-lucide="${name}" class="${cls}" aria-hidden="true"></i>`;
const root = document.querySelector<HTMLDivElement>('#app')!;
let screen: 'home' | 'processing' | 'result' = 'home';
let tab: 'message' | 'url' | 'audio' = 'message';
let message = '', urlsText = '', audioFile: File | undefined, audioUrl = '', audioDuration = 0;
let error = '', notice = '', busy = false, questionBusy = false;
let access: CaseAccess | undefined, result: Result | undefined;
let simulationId = '', remaining = 5;
let controller: AbortController | undefined;
let progress: Progress = { stage: 'queued', detail: 'Menunggu pemeriksaan.', completed: 0, total: 0 };
let conversations: { role: 'user' | 'assistant'; text: string; refs?: string[] }[] = [];
let pendingContext = '';
let flowVersion = 0;

const riskText: Record<Risk, string> = { high: 'Risiko tinggi', verify: 'Perlu verifikasi', low: 'Belum ditemukan indikator kuat', insufficient: 'Bukti belum cukup' };
const statusText: Record<string, string> = { done: 'Selesai', limited: 'Terbatas', unavailable: 'Belum tersedia', inconclusive: 'Belum pasti', skipped: 'Tidak diperiksa' };
const indicatorText: Record<string, string> = { urgency: 'Tekanan waktu', payment_request: 'Permintaan pembayaran', secrecy: 'Pembatasan verifikasi', impersonation: 'Klaim identitas', secret_request: 'Permintaan rahasia', protective_context: 'Konteks edukasi', url_warning: 'Struktur perlu diperiksa', url_unknown: 'Tujuan belum diketahui', structure: 'Struktur domain', source: 'Sumber isi', other: 'Perlu diperiksa' };

function header() {
  return `<header class="site-header"><a class="brand" href="#" aria-label="Sinyara, beranda"><img src="${import.meta.env.BASE_URL}favicon.svg" alt="" width="38" height="38"><span>sinyara<span class="brand-dot">.</span></span></a>
    <nav aria-label="Navigasi utama"><button class="nav-link" data-dialog="how">Cara kerja</button><button class="nav-link" data-dialog="privacy">Privasi</button><button class="nav-link" data-dialog="about">Tentang</button></nav>
    <div class="header-end">${screen === 'home' ? `<span class="header-note">${icon('shield-check')} Temani keputusanmu</span>` : `<button class="button small outline" id="new-case">${icon('plus')} Pemeriksaan baru</button>`}</div></header>`;
}

function home() {
  return `<section class="hero"><div class="eyebrow"><span></span> TEMAN PERIKSA DI DUNIA DIGITAL</div><h1>Ragu itu wajar.<br>Periksa dulu, <span>yuk.</span><svg class="underline" viewBox="0 0 130 13" aria-hidden="true"><path d="M3 8 Q60 -1 125 6 M12 12 Q72 5 112 10"/></svg></h1><p>Pesan mendadak, tautan asing, atau suara yang terasa akrab.<br class="desktop"> Ambil jeda. Kita periksa bersama.</p></section>
  <div class="workspace"><section class="input-card card" aria-labelledby="form-title"><div class="card-heading"><div><p class="eyebrow muted">MULAI DARI SINI</p><h2 id="form-title">Apa yang bikin kamu ragu?</h2></div><span class="step-count">01 / 03</span></div>
  <div class="tabs" role="tablist" aria-label="Jenis bukti">${(['message', 'url', 'audio'] as const).map(t => `<button id="tab-${t}" role="tab" aria-selected="${tab === t}" aria-controls="input-panel" tabindex="${tab === t ? 0 : -1}" data-tab="${t}" class="tab ${tab === t ? 'active' : ''}">${icon(t === 'message' ? 'message-square-text' : t === 'url' ? 'link' : 'audio-lines')}${t === 'message' ? 'Pesan' : t === 'url' ? 'Tautan' : 'Suara'}${(t === 'message' && message) || (t === 'url' && urlsText) || (t === 'audio' && audioFile) ? '<span class="input-dot" aria-label="berisi bukti"></span>' : ''}</button>`).join('')}</div>
  <form id="case-form"><div id="input-panel" role="tabpanel" aria-labelledby="tab-${tab}">${inputPanel()}</div>
  <div class="input-footer"><button class="text-button" type="button" id="add-evidence">${icon('plus')} Tambahkan bukti lain</button><span class="hint">${[message.trim() && 'pesan', urlsText.trim() && 'tautan', audioFile && 'suara'].filter(Boolean).length || 0}/3 jenis bukti</span></div>
  <div class="form-error ${error ? '' : 'hidden'}" id="form-error" role="alert" tabindex="-1">${error ? icon('circle-alert') + e(error) : ''}</div>
  <button class="button primary full" type="submit" ${busy ? 'disabled' : ''}>${busy ? 'Menyiapkan kasus…' : 'Periksa sekarang'} ${icon('arrow-right')}</button>
  <p class="form-caption">${icon('lock-keyhole')} Hanya untuk diperiksa. Tidak untuk melatih AI.</p>
  ${!client ? '<p class="mode-note">Purwarupa interaktif · Analisis input pribadi belum aktif.<br>Jelajahi tiga contoh simulasi di bawah.</p>' : `<p class="mode-note">Analisis ${backend === 'fastapi' ? 'lokal' : 'publik'} · 3 pemeriksaan per sesi / 24 jam.</p>`}</form></section>
  <aside class="companion"><div class="illustration" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><span class="deco-star">✳</span><div class="mini-message msg-one"><span class="mini-icon">${icon('message-square-text')}</span><div><span class="skeleton long"></span><span class="skeleton short"></span></div><span class="message-question">?</span></div><div class="illustration-shield">${icon('shield-check')}</div><div class="mini-message msg-two">${icon('check-check')} Ada waktu untuk memastikan.</div><span class="tiny-spark">✦</span></div>
  <div class="companion-copy"><span class="eyebrow">PERIKSA SEBELUM PERCAYA</span><h2>Sedikit jeda,<br>keputusan lebih terjaga.</h2><p>Kamu tidak harus menebak sendirian.<br>Sinyara membantumu melihat:</p><ul class="feature-list"><li>${icon('check')} Isi dan konteks permintaan</li><li>${icon('check')} Struktur tautan yang perlu dicek</li><li>${icon('check')} Isi suara & indikasi manipulasi</li></ul><button class="text-button" data-dialog="how">Kenali cara kerjanya ${icon('arrow-up-right')}</button></div></aside></div>
  <section class="examples" aria-labelledby="examples-title"><div class="section-heading"><h2 id="examples-title">Belum ada yang mau diperiksa?</h2><span>Coba satu cerita berikut <span aria-hidden="true">↙</span></span></div><div class="example-grid">${scenarios.map(s => `<button class="example-card" data-scenario="${s.id}"><span class="example-icon">${icon(s.icon)}</span><span><strong>${s.title}</strong><small>${s.description}</small></span>${icon('arrow-up-right')}</button>`).join('')}</div><p class="example-caption">Tiga skenario buatan · Contoh hasil — simulasi</p></section>`;
}

function inputPanel() {
  if (tab === 'message') return `<label for="message">Tempel pesan yang ingin kamu periksa</label><textarea id="message" name="message" maxlength="3000" rows="6" placeholder="Contoh: ‘Paket Anda tertahan. Segera transfer biaya pengiriman ulang…’" aria-describedby="message-hint char-count">${e(message)}</textarea><div class="field-meta"><span id="message-hint">Hapus data sensitif yang tidak diperlukan.</span><span id="char-count">${message.length.toLocaleString('id-ID')} / 3.000</span></div>`;
  if (tab === 'url') return `<label for="urls">Tempel tautan yang ingin kamu periksa</label><textarea id="urls" name="urls" rows="6" placeholder="https://contoh.com/pesan&#10;&#10;Satu tautan per baris, maksimal 3 tautan." aria-describedby="url-hint">${e(urlsText)}</textarea><div class="field-meta" id="url-hint"><span>Hanya HTTP/HTTPS. Halaman tujuan tidak dibuka.</span><span>Maks. 3</span></div>`;
  return `<label for="audio-file">Tambahkan rekaman yang sudah kamu miliki</label><label class="upload-zone ${audioFile ? 'has-file' : ''}" for="audio-file"><span class="upload-icon">${icon(audioFile ? 'audio-lines' : 'upload')}</span><strong>${audioFile ? e(audioFile.name) : 'Pilih atau letakkan rekaman di sini'}</strong><span>${audioFile ? `${(audioFile.size / 1024 / 1024).toFixed(1)} MB · ${timeLabel(audioDuration)}` : 'WAV, MP3, M4A, OGG, atau OPUS'}</span><small>Maksimal 60 detik · 10 MB</small><input id="audio-file" type="file" accept=".wav,.mp3,.m4a,.ogg,.opus,audio/*"></label>${audioUrl ? `<audio controls src="${e(audioUrl)}" class="input-audio" aria-label="Pratinjau rekaman"></audio><button class="text-button" id="remove-audio" type="button">${icon('x')} Lepas rekaman</button>` : ''}<div class="field-meta"><span>Isi percakapan dan keaslian suara dinilai terpisah.</span></div>`;
}

function processing() {
  const percent = progress.total ? Math.round(progress.completed / progress.total * 100) : undefined;
  const stages = [ ['queued', 'Masuk antrean'], ['urls', 'Memeriksa bukti'], ['language', 'Memahami konteks'], ['validation', 'Menyusun hasil'] ];
  return `<section class="processing card"><span class="eyebrow">${simulationId ? 'CONTOH HASIL — SIMULASI' : 'PEMERIKSAAN BERLANGSUNG'}</span><div class="scanner" aria-hidden="true">${icon('shield-check')}<span></span></div><h1>Kita periksa satu per satu.</h1><p id="progress-detail" role="status">${e(progress.detail)}</p><div class="progress-track" role="progressbar" aria-label="Tahap pemeriksaan selesai" aria-valuemin="0" aria-valuemax="100" ${percent !== undefined ? `aria-valuenow="${percent}"` : ''}><span style="width:${percent ?? 6}%" class="${percent === undefined ? 'indeterminate' : ''}"></span></div><div class="progress-meta"><span>${simulationId ? 'Alur contoh, bukan waktu inferensi model' : 'Progres berdasarkan tahap yang selesai'}</span><strong>${percent === undefined ? (progress.queue_position ? `Antrean ${progress.queue_position}` : 'Menunggu') : `${percent}%`}</strong></div><div class="stage-list">${stages.map(([key, label]) => `<div class="${progress.stage === key ? 'current' : ''}"><span></span>${label}</div>`).join('')}</div><p class="muted processing-note">${simulationId ? 'Skenario buatan untuk mengenali cara kerja Sinyara.' : 'Model lokal dapat memerlukan beberapa menit. Kamu bisa membatalkan dan menghapus kasus.'}</p><button class="text-button" id="cancel">${icon('x')} Batalkan pemeriksaan</button></section>`;
}

function results() {
  const r = result!;
  return `<div class="result-top"><div><div class="eyebrow">${r.mode === 'simulation' ? 'CONTOH HASIL — SIMULASI' : 'HASIL PEMERIKSAAN'} <span class="case-tag">${e(r.case_id.slice(0, 12))} · revisi ${r.revision}</span></div><h1>Lebih jelas, lebih tenang.</h1></div><span class="expiry-note">${icon('lock-keyhole')} ${r.mode === 'simulation' ? 'Skenario buatan' : 'Sementara · 15 menit tidak aktif'}</span></div>
  ${notice ? `<div class="notice" role="status">${e(notice)}</div>` : ''}${error ? `<div class="form-error" role="alert">${icon('circle-alert')}${e(error)}</div>` : ''}
  <section class="risk-card risk-${r.risk}" aria-labelledby="risk-heading"><span class="risk-icon">${icon(r.risk === 'low' ? 'shield-check' : 'circle-alert')}</span><div><div class="risk-label" id="risk-heading">${riskText[r.risk]}</div><h2>${e(r.summary)}</h2><p>${r.mode === 'simulation' ? 'Ini contoh terkurasi. Input pribadimu tidak digunakan dalam hasil ini.' : 'Baca bukti dan keterbatasan sebelum mengambil keputusan.'}</p></div><span class="risk-emblem" aria-hidden="true">${icon('shield-check')}</span></section>
  <div class="result-grid"><div class="evidence-column"><section class="card evidence-card"><div class="section-heading"><h2>Bukti yang bisa kamu cek</h2><span>${r.evidence.length} temuan</span></div><p class="section-description">${r.mode === 'simulation' ? 'Kutipan dari naskah skenario.' : 'Kutipan dari sumber yang kamu berikan. Cocokkan dengan konteks aslinya.'}</p><div class="evidence-list">${r.evidence.length ? r.evidence.map(ev => `<article class="evidence" id="evidence-${e(ev.id)}"><div class="evidence-meta"><span>${icon(ev.source === 'audio' ? 'audio-lines' : ev.source === 'url' ? 'link' : 'message-square-text')}${ev.source === 'audio' ? 'Rekaman' : ev.source === 'url' ? 'Tautan' : ev.source === 'context' ? 'Konteks pengguna' : 'Pesan'}</span><span class="indicator">${e(indicatorText[ev.indicator] || 'Perlu diperiksa')}</span></div><button class="quote-button" data-evidence="${e(ev.id)}" title="Sorot kutipan ini"><q>${e(ev.quote)}</q></button><p>${e(ev.explanation)}</p><div class="evidence-bottom"><span class="evidence-id">[${e(ev.id)}]</span>${ev.start != null && ev.end != null ? `<button class="timestamp text-button" data-seek="${ev.start}" data-end="${ev.end}">${icon('play')} ${timeLabel(ev.start)}–${timeLabel(ev.end)}</button>` : ''}</div></article>`).join('') : '<div class="empty-evidence">Belum ada bukti yang dapat dirujuk. Lihat status pemeriksaan berikut.</div>'}</div>${audioUrl && r.mode === 'real' ? `<audio id="result-audio" controls src="${e(audioUrl)}" aria-label="Putar rekaman asli"></audio>` : ''}</section>
  <section class="card checks-card"><h2>Yang sudah diperiksa</h2>${r.checks.map(c => `<div class="check-row"><span class="check-status-icon ${c.status}">${icon(c.status === 'done' ? 'check' : c.status === 'skipped' ? 'circle-help' : 'info')}</span><div><strong>${e(c.title)}</strong><p>${e(c.detail)}</p></div><span class="status-pill ${c.status}">${statusText[c.status]}</span></div>`).join('')}</section>
  <details class="card limitations"><summary>${icon('circle-help')} Batas pemeriksaan ini ${icon('chevron-down')}</summary><ul>${r.limitations.map(l => `<li>${e(l)}</li>`).join('')}</ul><p class="model-caption">${Object.entries(r.models).map(([key, value]) => `${e(key)}: ${e(value)}`).join(' · ') || 'Tidak ada model yang menyelesaikan pemeriksaan.'}</p></details></div>
  <aside class="chat-card card" aria-labelledby="chat-title"><div class="chat-heading"><span class="chat-symbol">${icon('sparkles')}</span><div><h2 id="chat-title">Kita bahas bersama.</h2><p>Tanya tentang hasil pemeriksaanmu.</p></div></div><div class="chat-messages" id="chat-messages" aria-live="polite"><div class="chat-bubble assistant">${r.mode === 'simulation' ? 'Kamu sedang mencoba percakapan simulasi. Jawaban memakai pola contoh, tanpa model AI.' : 'Aku bisa membantumu membaca bukti. Apa yang ingin kamu pahami lebih jauh?'}<span>Sinyara ${r.mode === 'simulation' ? '· contoh' : ''}</span></div>${conversations.map(m => `<div class="chat-bubble ${m.role}"><p>${e(m.text)}</p>${m.refs?.length ? `<div class="chat-refs">${m.refs.map(id => `<button data-ref="${e(id)}">[${e(id)}]</button>`).join('')}</div>` : ''}<span>${m.role === 'user' ? 'Kamu' : 'Sinyara'}</span></div>`).join('')}${questionBusy ? '<div class="chat-bubble assistant"><span class="typing">Membaca kembali bukti…</span></div>' : ''}</div>
  <div class="suggestions">${['Kenapa perlu dicurigai?', 'Apa langkah berikutnya?'].map(q => `<button data-question="${q}" ${questionBusy || !remaining ? 'disabled' : ''}>${q} ${icon('arrow-up-right')}</button>`).join('')}</div><form id="chat-form"><label class="sr-only" for="question">Pertanyaan tentang hasil</label><div class="chat-input"><textarea id="question" maxlength="1000" rows="2" placeholder="Tanyakan tentang bukti…" ${questionBusy || !remaining ? 'disabled' : ''}></textarea><button class="send-button" aria-label="Kirim pertanyaan" type="submit" ${questionBusy || !remaining ? 'disabled' : ''}>${icon('arrow-right')}</button></div><details class="context-detail"><summary>+ Tambahkan konteks untuk ditinjau ulang</summary><label class="sr-only" for="context">Konteks tambahan, bukan perintah untuk model</label><textarea id="context" rows="2" maxlength="2000" placeholder="Contoh: pengirim mengaku keluarga saya…" ${questionBusy ? 'disabled' : ''}>${e(pendingContext)}</textarea><p>Keterangan tambahan akan diperlakukan sebagai klaim pengguna.</p></details><p class="chat-caption">${remaining} dari 5 pertanyaan tersisa ${r.mode === 'simulation' ? '· simulasi' : '· berbasis bukti kasus'}</p></form></aside></div>
  <section class="next-steps card"><div><span class="eyebrow">SEBELUM MELANJUTKAN</span><h2>Ambil langkah yang lebih terjaga.</h2></div><ol>${r.next_steps.map((s, i) => `<li><span>0${i + 1}</span>${e(s)}</li>`).join('')}</ol><div class="result-actions"><button class="button outline" id="export">${icon('download')} Ekspor ringkasan</button><button class="text-button danger" id="delete">${icon('trash-2')} Hapus kasus</button><span>Nomor, email, dan tautan disamarkan saat ekspor.</span></div></section>`;
}

function render(focus?: string) {
  root.innerHTML = `${header()}<main id="main-content">${screen === 'home' ? home() : screen === 'processing' ? processing() : results()}</main><footer><div class="footer-brand"><strong>sinyara.</strong><span>Periksa sebelum percaya.</span></div><p>Teknologi membantu. Verifikasi tetap di tanganmu.</p><span>Purwarupa v0.1 <span aria-hidden="true">↗</span></span></footer><dialog id="info-dialog"><button class="dialog-close" aria-label="Tutup informasi">${icon('x')}</button><div id="dialog-body"></div></dialog>`;
  createIcons({ icons, attrs: { 'stroke-width': 1.7 } });
  bind();
  if (focus) document.querySelector<HTMLElement>(focus)?.focus();
}

function updateProgress(p: Progress) {
  progress = p;
  if (screen !== 'processing') return;
  const view = root.querySelector('.processing');
  if (!view) { render(); return; }
  // Update only progress nodes so keyboard focus on Cancel survives polling.
  const percent = p.total ? Math.round(p.completed / p.total * 100) : undefined;
  view.querySelector('#progress-detail')!.textContent = p.detail;
  const bar = view.querySelector<HTMLElement>('[role="progressbar"]')!;
  if (percent !== undefined) bar.setAttribute('aria-valuenow', String(percent));
  else bar.removeAttribute('aria-valuenow');
  const fill = bar.querySelector<HTMLElement>('span')!;
  fill.style.width = `${percent ?? 6}%`;
  fill.classList.toggle('indeterminate', percent === undefined);
  view.querySelector('.progress-meta strong')!.textContent = percent === undefined ? (p.queue_position ? `Antrean ${p.queue_position}` : 'Menunggu') : `${percent}%`;
  const keys = ['queued', 'urls', 'language', 'validation'];
  view.querySelectorAll('.stage-list>div').forEach((el, i) => el.classList.toggle('current', keys[i] === p.stage));
}

async function runScenario(id: string) {
  if (busy) return;
  const version = ++flowVersion;
  simulationId = id; access = undefined; screen = 'processing'; busy = true; error = ''; notice = ''; conversations = []; remaining = 5;
  controller = new AbortController();
  const signal = controller.signal;
  try {
    const stages = ['queued', 'urls', 'language', 'validation'];
    const details = ['Simulasi: menyiapkan skenario contoh.', 'Simulasi: membaca bukti pada naskah.', 'Simulasi: meninjau konteks permintaan.', 'Simulasi: menyusun contoh hasil.'];
    for (let i = 0; i < stages.length; i++) {
      if (signal.aborted) return;
      updateProgress({ stage: stages[i], detail: details[i], completed: i, total: 4 });
      await new Promise(resolve => setTimeout(resolve, 400));
    }
    if (!signal.aborted) { result = fixture(id); screen = 'result'; busy = false; render(); window.scrollTo({ top: 0, behavior: 'instant' }); }
  } finally { if (version === flowVersion) busy = false; }
}

async function fileToInput(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return { name: file.name, base64: btoa(binary) };
}

async function submit() {
  if (busy) return;
  const urls = urlsText.split(/\r?\n/).map(u => u.trim()).filter(Boolean);
  error = validateForm(message, urls, !!audioFile) || '';
  if (!error && !client) error = 'Analisis input pribadi belum terhubung di purwarupa ini. Pilih salah satu contoh simulasi di bawah; pesanmu belum dikirim ke server.';
  if (error) { render('#form-error'); return; }
  busy = true; simulationId = ''; notice = ''; conversations = []; remaining = 5;
  try {
    render();
    const input: CaseInput = { message, urls, ...(audioFile ? { audio: await fileToInput(audioFile) } : {}) };
    access = await client!.createCase(input);
    screen = 'processing'; controller = new AbortController();
    progress = { stage: 'queued', detail: 'Memasukkan kasus ke antrean.', completed: 0, total: 0 }; render();
    result = await client!.analyzeCase(access, updateProgress, controller.signal);
    screen = 'result'; busy = false; render(); window.scrollTo({ top: 0, behavior: 'instant' });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return;
    error = err instanceof Error ? err.message : 'Pemeriksaan belum dapat dilanjutkan.';
    if (access && client) {
      try { await client.deleteCase(access); access = undefined; } catch { /* Server TTL remains the fallback when unreachable. */ }
    }
    busy = false; screen = 'home'; render('#form-error');
  }
}

async function setAudio(file: File) {
  error = '';
  if (file.size > 10 * 1024 * 1024 || file.size === 0) error = 'Ukuran rekaman harus antara 1 byte dan 10 MB.';
  if (!/\.(wav|mp3|m4a|ogg|opus)$/i.test(file.name)) error = 'Gunakan WAV, MP3, M4A, OGG, atau OPUS.';
  if (error) { render(); return; }
  const url = URL.createObjectURL(file);
  const probe = new Audio(url);
  try {
    const duration = await new Promise<number>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Metadata rekaman belum dapat dibaca. Coba file lain.')), 8000);
      probe.onloadedmetadata = () => { clearTimeout(timeout); resolve(probe.duration); };
      probe.onerror = () => { clearTimeout(timeout); reject(new Error('Rekaman tidak dapat diputar di browser ini. Coba format WAV atau MP3.')); };
    });
    if (!Number.isFinite(duration) || duration > 60.05) throw new Error('Durasi rekaman maksimal 60 detik.');
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    audioFile = file; audioUrl = url; audioDuration = duration;
  } catch (err) { URL.revokeObjectURL(url); error = (err as Error).message; }
  finally { probe.removeAttribute('src'); probe.load(); }
  render();
}

async function ask(question: string) {
  if (!question.trim() || questionBusy || !remaining || !result) return;
  const version = flowVersion;
  questionBusy = true; error = ''; pendingContext = (document.querySelector<HTMLTextAreaElement>('#context')?.value || '').trim();
  conversations.push({ role: 'user', text: question + (pendingContext ? `\n\nKonteks tambahan: ${pendingContext}` : '') }); render();
  try {
    const answer = result.mode === 'simulation' ? fixtureAnswer(question, result, remaining - 1) : await client!.askFollowup(access!, question, pendingContext);
    if (version !== flowVersion) return;
    conversations.push({ role: 'assistant', text: answer.answer, refs: answer.evidence_ids }); remaining = answer.remaining;
    if (pendingContext && result.mode === 'real') {
      // Reuse analyzeCase's idempotent status read to obtain revised assessment.
      result = await client!.analyzeCase(access!, () => {}, new AbortController().signal);
    }
    if (pendingContext && result.mode === 'simulation') notice = 'Konteks tambahan disimpan dalam percakapan contoh. Penilaian simulasi tidak berubah karena model belum dijalankan.';
    pendingContext = '';
  } catch (err) { if (version === flowVersion) { error = (err as Error).message; if (err instanceof ClientError && err.code === 'followup_quota') remaining = 0; } }
  finally { if (version === flowVersion) { questionBusy = false; render(); document.querySelector('#chat-messages')?.scrollTo({ top: 99999 }); } }
}

async function removeCase(clear = true) {
  flowVersion++;
  controller?.abort();
  if (access && client) {
    try { await client.deleteCase(access); }
    catch (err) { if (!(err instanceof ClientError && err.code === 'expired')) { error = `Penghapusan belum terkonfirmasi: ${(err as Error).message}`; busy = false; render(); return; } }
  }
  access = undefined; result = undefined; simulationId = ''; conversations = []; error = ''; screen = 'home'; busy = false; questionBusy = false;
  if (clear) { message = ''; urlsText = ''; audioFile = undefined; if (audioUrl) URL.revokeObjectURL(audioUrl); audioUrl = ''; audioDuration = 0; }
  render(); window.scrollTo({ top: 0, behavior: 'instant' });
}

function showDialog(kind: string) {
  const content: Record<string, string> = {
    how: `<span class="eyebrow">CARA KERJA</span><h2>Jeda sejenak. Lihat lebih jelas.</h2><ol class="how-list"><li><strong>Tambahkan yang bikin ragu.</strong><p>Pesan, hingga tiga tautan, dan satu rekaman bisa menjadi satu kasus.</p></li><li><strong>Periksa indikatornya.</strong><p>Sinyara meninjau isi, struktur tautan, dan audio secara terpisah. Tahap yang gagal tetap terlihat.</p></li><li><strong>Pahami bukti. Lalu verifikasi.</strong><p>Baca kutipan sumber, tanyakan konteks, lalu hubungi pihak terkait lewat kanal resmi.</p></li></ol><p class="dialog-note">Prototipe publik memuat tiga simulasi. Analisis nyata memerlukan backend yang terhubung. Persentase adalah jumlah tahap selesai, bukan tingkat keyakinan.</p>`,
    privacy: `<span class="eyebrow">PRIVASI</span><h2>Cukup untuk diperiksa.</h2><p>Di mode contoh, teks dan rekaman tetap di browser. Memilih skenario contoh tidak mengirim input pribadimu.</p><p>Jika backend terhubung, input dikirim untuk pemeriksaan. Kasus dan audio disimpan sementara di memori server, dihapus setelah 15 menit tidak aktif, dan hilang saat server dimulai ulang. Polling otomatis tidak memperpanjang masa simpan.</p><p>Token kasus disimpan dalam memori halaman, bukan URL. Rekaman diputar dari salinan lokal browser. Unggahan tidak digunakan untuk melatih model secara otomatis. Log aplikasi tidak memuat isi pesan.</p><p>Provider hosting dapat memiliki log dan kebijakan sendiri. Hapus data sensitif yang tidak diperlukan sebelum mengirim. Kuota sesi adalah pembatas demo dan dapat direset dengan mengganti sesi browser.</p><p class="dialog-note">Tombol Hapus kasus menghapus data kasus di server. Pekerjaan model yang sedang berjalan melepaskan salinan kerjanya setelah berhenti. Tutup atau muat ulang tab untuk melepaskan input lokal.</p>`,
    about: `<span class="eyebrow">TENTANG SINYARA</span><h2>Periksa sebelum percaya.</h2><p>Sinyara adalah proyek portofolio AI untuk membantu masyarakat dan keluarga memahami indikator penipuan digital dalam bahasa Indonesia.</p><p>Hasil menyertakan bukti, keterbatasan, dan langkah verifikasi. Tidak ada skor kepastian semu: deteksi suara sintetis masih eksperimental dan belum dikalibrasi pada rekaman Indonesia.</p><p>Nama Sinyara adalah nama kerja. Pemeriksaan merek dan domain dilakukan sebelum peluncuran komersial.</p><p class="dialog-note">v0.1 · HTML, TypeScript, FastAPI, Ollama. Model dan konfigurasi yang benar-benar digunakan tercantum pada setiap hasil.</p>`,
  };
  document.querySelector('#dialog-body')!.innerHTML = content[kind] || content.about;
  document.querySelector<HTMLDialogElement>('#info-dialog')!.showModal();
}

function exportResult() {
  if (!result) return;
  const r = result;
  const text = `SINYARA — Periksa sebelum percaya\n${r.mode === 'simulation' ? 'CONTOH HASIL — SIMULASI' : 'HASIL PEMERIKSAAN'}\n${riskText[r.risk]}\n${r.summary}\n\nBUKTI\n${r.evidence.map(ev => `[${ev.id}] ${ev.quote}\n${ev.explanation}`).join('\n\n')}\n\nPEMERIKSAAN\n${r.checks.map(c => `${c.title}: ${statusText[c.status]} — ${c.detail}`).join('\n')}\n\nKETERBATASAN\n${r.limitations.join('\n')}\n\nLANGKAH BERIKUTNYA\n${r.next_steps.join('\n')}\n\nMODEL\n${JSON.stringify(r.models)}\n\nPenyamaran otomatis bersifat upaya terbaik. Periksa kembali sebelum membagikan ringkasan.\n`;
  const url = URL.createObjectURL(new Blob([redact(text)], { type: 'text/plain;charset=utf-8' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'ringkasan-sinyara.txt'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function bind() {
  document.querySelectorAll<HTMLElement>('[data-dialog]').forEach(el => el.onclick = () => showDialog(el.dataset.dialog!));
  document.querySelector('.dialog-close')?.addEventListener('click', () => document.querySelector<HTMLDialogElement>('dialog')?.close());
  document.querySelector<HTMLAnchorElement>('.brand')!.onclick = event => { event.preventDefault(); if (screen !== 'home') void removeCase(); };
  document.querySelectorAll<HTMLElement>('[data-tab]').forEach(el => el.onclick = () => { tab = el.dataset.tab as typeof tab; error = ''; render(`#tab-${tab}`); });
  document.querySelector('.tabs')?.addEventListener('keydown', event => {
    const key = (event as KeyboardEvent).key;
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)) return;
    event.preventDefault(); const tabs = ['message', 'url', 'audio'] as const; const current = tabs.indexOf(tab);
    tab = tabs[key === 'Home' ? 0 : key === 'End' ? 2 : (current + (key === 'ArrowRight' ? 1 : 2)) % 3]; render(`#tab-${tab}`);
  });
  document.querySelector<HTMLTextAreaElement>('#message')?.addEventListener('input', event => { message = (event.target as HTMLTextAreaElement).value; document.querySelector('#char-count')!.textContent = `${message.length.toLocaleString('id-ID')} / 3.000`; });
  document.querySelector<HTMLTextAreaElement>('#urls')?.addEventListener('input', event => { urlsText = (event.target as HTMLTextAreaElement).value; });
  document.querySelector('#case-form')?.addEventListener('submit', event => { event.preventDefault(); void submit(); });
  document.querySelector('#add-evidence')?.addEventListener('click', () => { tab = tab === 'message' ? 'url' : tab === 'url' ? 'audio' : 'message'; render(`#tab-${tab}`); });
  document.querySelector<HTMLInputElement>('#audio-file')?.addEventListener('change', event => { const file = (event.target as HTMLInputElement).files?.[0]; if (file) void setAudio(file); });
  const zone = document.querySelector<HTMLElement>('.upload-zone');
  zone?.addEventListener('dragover', event => { event.preventDefault(); zone.classList.add('dragover'); });
  zone?.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone?.addEventListener('drop', event => { event.preventDefault(); const file = event.dataTransfer?.files[0]; if (file) void setAudio(file); });
  document.querySelector('#remove-audio')?.addEventListener('click', () => { if (audioUrl) URL.revokeObjectURL(audioUrl); audioUrl = ''; audioFile = undefined; render(); });
  document.querySelectorAll<HTMLElement>('[data-scenario]').forEach(el => el.onclick = () => void runScenario(el.dataset.scenario!));
  document.querySelector('#cancel')?.addEventListener('click', () => void removeCase(false));
  document.querySelector('#new-case')?.addEventListener('click', () => void removeCase());
  document.querySelector('#delete')?.addEventListener('click', () => void removeCase());
  document.querySelector('#export')?.addEventListener('click', exportResult);
  document.querySelector('#chat-form')?.addEventListener('submit', event => { event.preventDefault(); const question = document.querySelector<HTMLTextAreaElement>('#question')?.value; if (question) void ask(question); });
  document.querySelectorAll<HTMLElement>('[data-question]').forEach(el => el.onclick = () => void ask(el.dataset.question!));
  document.querySelectorAll<HTMLElement>('[data-evidence]').forEach(el => el.onclick = () => el.closest('.evidence')?.classList.toggle('highlight'));
  document.querySelectorAll<HTMLElement>('[data-ref]').forEach(el => el.onclick = () => { const target = document.getElementById(`evidence-${el.dataset.ref}`); if (target) { target.classList.add('highlight'); target.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'center' }); } else { notice = 'Referensi ini berasal dari konteks tambahan pengguna yang tercantum pada percakapan.'; render(); } });
  document.querySelectorAll<HTMLElement>('[data-seek]').forEach(el => el.onclick = () => { const audio = document.querySelector<HTMLAudioElement>('#result-audio'); if (!audio) { notice = 'Contoh ini hanya berisi naskah. Rekaman audio tidak disertakan.'; render(); return; } audio.currentTime = Number(el.dataset.seek); const end = Number(el.dataset.end); audio.ontimeupdate = () => { if (audio.currentTime >= end) { audio.pause(); audio.ontimeupdate = null; } }; void audio.play().catch(() => { notice = 'Tekan tombol putar pada pemutar rekaman.'; render(); }); });
}

render();
