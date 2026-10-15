// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';

it('does not display a previous case result when a pending poll is cancelled', async () => {
  vi.stubEnv('VITE_BACKEND', 'fastapi');
  let finishPoll!: (value: unknown) => void;
  let pollStarted!: () => void;
  const started = new Promise<void>(resolve => { pollStarted = resolve; });
  vi.stubGlobal('fetch', vi.fn(async (_url, options) => {
    if (options.method === 'POST') return { ok: true, json: async () => ({ status: 'queued' }) };
    const data = new Promise(resolve => { finishPoll = resolve; });
    pollStarted();
    return { ok: true, json: () => data };
  }));
  const { client } = await import('../../src/client');
  const progress = vi.fn();
  const controller = new AbortController();
  const pending = client!.analyzeCase({ case_id: 'previous-case', token: 'test-access-token' }, progress, controller.signal);
  await started;
  controller.abort();
  finishPoll({ status: 'done', progress: { stage: 'done', completed: 3, total: 3 }, result: { case_id: 'previous-case', mode: 'real' } });
  await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  expect(progress).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
