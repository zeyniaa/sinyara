import type { Answer, CaseAccess, CaseClient, CaseInput, Progress, Result, Snapshot } from './types';

export class ClientError extends Error {
  constructor(public code: string, message: string) { super(message); }
}

let session = sessionStorage.getItem('sinyara-session');
if (!session) { session = crypto.randomUUID(); sessionStorage.setItem('sinyara-session', session); }

export const backend = import.meta.env.VITE_BACKEND || 'simulation';
const base = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8010').replace(/\/$/, '');

async function request<T>(path: string, method = 'GET', body?: unknown, access?: CaseAccess): Promise<T> {
  try {
    const response = await fetch(base + path, { method, headers: { 'Content-Type': 'application/json', 'X-Sinyara-Session': session!, ...(access ? { Authorization: `Bearer ${access.token}` } : {}) }, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
    const data = await response.json();
    if (!response.ok) throw new ClientError(data.error?.code || 'unavailable', data.error?.message || 'Pemeriksaan belum dapat dilanjutkan.');
    return data as T;
  } catch (error) {
    if (error instanceof ClientError) throw error;
    throw new ClientError('unavailable', 'Backend belum terhubung. Pastikan layanan Sinyara lokal berjalan, atau coba contoh simulasi.');
  }
}

function pause(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
    const abort = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')); };
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort();
  });
}

async function poll(get: () => Promise<Snapshot>, onProgress: (p: Progress) => void, signal: AbortSignal): Promise<Result> {
  while (!signal.aborted) {
    const snapshot = await get();
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
    onProgress(snapshot.progress);
    if (snapshot.status === 'done' && snapshot.result) return snapshot.result;
    if (snapshot.status === 'error') throw new ClientError(snapshot.error?.code || 'model_error', snapshot.error?.message || 'Pemeriksaan gagal.');
    await pause(900, signal);
  }
  throw new DOMException('Aborted', 'AbortError');
}

class FastApiClient implements CaseClient {
  createCase(input: CaseInput) { return request<CaseAccess>('/v1/cases', 'POST', input); }
  async analyzeCase(a: CaseAccess, cb: (p: Progress) => void, signal: AbortSignal) {
    await request(`/v1/cases/${a.case_id}/analyze`, 'POST', undefined, a);
    return poll(() => request<Snapshot>(`/v1/cases/${a.case_id}`, 'GET', undefined, a), cb, signal);
  }
  askFollowup(a: CaseAccess, question: string, context = '') { return request<Answer>(`/v1/cases/${a.case_id}/followups`, 'POST', { question, context }, a); }
  deleteCase(a: CaseAccess) { return request<void>(`/v1/cases/${a.case_id}`, 'DELETE', undefined, a); }
}

class GradioClient implements CaseClient {
  private connection?: Promise<import('@gradio/client').Client>;
  private async call<T>(operation: string, data: unknown): Promise<T> {
    try {
      this.connection ??= import('@gradio/client').then(({ Client }) => Client.connect(import.meta.env.VITE_SPACE, { record_history: false }));
      const connection = await this.connection;
      const result = await connection.predict('/dispatch', { operation, payload: JSON.stringify(data) });
      const output = JSON.parse((result.data as string[])[0]);
      if (output.error) throw new ClientError(output.error.code, output.error.message);
      return output as T;
    } catch (error) {
      if (error instanceof ClientError) throw error;
      throw new ClientError('unavailable', 'Backend AI publik belum tersedia atau kuota penyedia sedang habis. Coba lagi nanti.');
    }
  }
  createCase(input: CaseInput) { return this.call<CaseAccess>('createCase', { input, session }); }
  async analyzeCase(a: CaseAccess, cb: (p: Progress) => void, signal: AbortSignal) {
    this.connection ??= import('@gradio/client').then(({ Client }) => Client.connect(import.meta.env.VITE_SPACE, { record_history: false }));
    try {
      const connection = await this.connection;
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      const job = connection.submit('/dispatch', { operation: 'analyzeCase', payload: JSON.stringify({ access: a }) });
      const abort = () => { void job.cancel(); };
      signal.addEventListener('abort', abort, { once: true });
      try {
        for await (const event of job) {
          if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
          if (event.type !== 'data') continue;
          const snapshot = JSON.parse((event.data as string[])[0]) as Snapshot & { error?: { code: string; message: string } };
          if (snapshot.error) throw new ClientError(snapshot.error.code, snapshot.error.message);
          cb(snapshot.progress);
          if (snapshot.status === 'done' && snapshot.result) return snapshot.result;
        }
      } finally { signal.removeEventListener('abort', abort); }
      throw new ClientError('model_error', 'Pemeriksaan berakhir sebelum hasil tersedia.');
    } catch (error) {
      if (error instanceof ClientError || error instanceof DOMException) throw error;
      throw new ClientError('unavailable', 'Backend publik sedang tidak tersedia atau kuota penyedia habis.');
    }
  }
  askFollowup(a: CaseAccess, question: string, context = '') { return this.call<Answer>('askFollowup', { access: a, question, context }); }
  async deleteCase(a: CaseAccess) { await this.call('deleteCase', { access: a }); }
}

export const client: CaseClient | undefined = backend === 'fastapi' ? new FastApiClient() : backend === 'gradio' ? new GradioClient() : undefined;
