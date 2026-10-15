export const escapeHtml = (value: unknown): string => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
export const timeLabel = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
export function validateForm(message: string, urls: string[], hasAudio: boolean): string | undefined {
  if (!message.trim() && !urls.length && !hasAudio) return 'Tambahkan pesan, tautan, atau rekaman terlebih dahulu.';
  if (message.length > 3000) return 'Pesan maksimal 3.000 karakter.';
  if (urls.length > 3) return 'Tambahkan maksimal 3 tautan.';
  for (const url of urls) {
    try { const parsed = new URL(url); if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname || /[\s\\]/.test(url) || url.length > 2048) throw new Error(); }
    catch { return 'Masukkan tautan HTTP atau HTTPS yang valid, satu tautan per baris.'; }
  }
}

export function redact(value: string): string {
  return value.replace(/https?:\/\/[^\s)]+/g, '[tautan disamarkan]')
    .replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, '[email disamarkan]')
    .replace(/(?:\+?\d[\d .-]{4,}\d)/g, '[nomor disamarkan]')
    .replace(/\b(otp|pin|password|kata sandi)\s*[:=]?\s*\S+/gi, '$1 [disamarkan]');
}
