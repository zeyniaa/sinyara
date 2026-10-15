// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, getByRole, getByLabelText, screen } from '@testing-library/dom';

beforeAll(async () => {
  vi.stubEnv('VITE_BACKEND', 'simulation');
  window.scrollTo = vi.fn();
  Element.prototype.scrollTo = vi.fn();
  document.body.innerHTML = '<div id="app"></div>';
  await import('../../src/main');
});

describe('prototype interactions', () => {
  it('keeps text when changing input tabs and supports arrow navigation', () => {
    fireEvent.input(getByLabelText(document.body, 'Tempel pesan yang ingin kamu periksa'), { target: { value: 'Pesan keluarga yang sah.' } });
    fireEvent.click(getByRole(document.body, 'tab', { name: 'Tautan' }));
    fireEvent.input(getByLabelText(document.body, 'Tempel tautan yang ingin kamu periksa'), { target: { value: 'https://example.com' } });
    fireEvent.keyDown(getByRole(document.body, 'tab', { name: 'Tautan' }), { key: 'ArrowLeft' });
    expect((getByLabelText(document.body, 'Tempel pesan yang ingin kamu periksa') as HTMLTextAreaElement).value).toBe('Pesan keluarga yang sah.');
  });
  it('does not fabricate verdicts for user input when disconnected', () => {
    fireEvent.submit(document.querySelector('#case-form')!);
    expect(screen.getByRole('alert').textContent).toContain('belum terhubung');
    expect(document.querySelector('.risk-card')).toBeNull();
  });
  it('renders all result and follow-up states as simulation', async () => {
    vi.useFakeTimers();
    fireEvent.click(getByRole(document.body, 'button', { name: /Pengingat dari keluarga/ }));
    expect(document.body.textContent).toContain('CONTOH HASIL — SIMULASI');
    const cancel = document.querySelector<HTMLButtonElement>('#cancel')!;
    cancel.focus();
    await vi.advanceTimersByTimeAsync(400);
    expect(document.activeElement).toBe(cancel);
    await vi.advanceTimersByTimeAsync(1400);
    expect(document.querySelector('.risk-card')?.textContent).toContain('Belum ditemukan indikator kuat');
    fireEvent.click(getByRole(document.body, 'button', { name: /Kenapa perlu dicurigai/ }));
    await vi.advanceTimersByTimeAsync(1);
    expect(document.querySelector('.chat-messages')?.textContent).toContain('Contoh jawaban — simulasi');
    expect(document.querySelector('.chat-caption')?.textContent).toContain('4 dari 5');
    vi.useRealTimers();
  });
});
