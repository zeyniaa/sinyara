// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { escapeHtml, redact, validateForm } from '../../src/utils';
import { fixture, fixtureAnswer, scenarios } from '../../src/fixtures';

describe('input and evidence boundaries', () => {
  it('rejects absent, long or unsafe input', () => {
    expect(validateForm('', [], false)).toBeTruthy();
    expect(validateForm('a'.repeat(3001), [], false)).toBeTruthy();
    expect(validateForm('', ['javascript:alert(1)'], false)).toBeTruthy();
    expect(validateForm('', ['https://example.com'], false)).toBeUndefined();
    expect(validateForm('', [], true)).toBeUndefined();
  });
  it('escapes untrusted messages rather than creating executable markup', () => {
    const node = document.createElement('div');
    node.innerHTML = escapeHtml('<img src=x onerror="alert(1)">');
    expect(node.querySelector('img')).toBeNull();
    expect(node.textContent).toBe('<img src=x onerror="alert(1)">');
  });
  it('redacts contacts, numbers and live URLs from exports', () => {
    const output = redact('Hubungi +62 812-1234-5678, a@example.com, https://example.com/?token=secret, OTP: 123456');
    expect(output).not.toContain('812'); expect(output).not.toContain('a@example.com');
    expect(output).not.toContain('https://'); expect(output).not.toContain('123456');
  });
  it('labels every curated result and reply as simulation', () => {
    for (const scenario of scenarios) {
      const result = fixture(scenario.id);
      expect(result.mode).toBe('simulation');
      expect(fixtureAnswer('Kenapa?', result, 4).answer).toContain('simulasi');
      expect(result.evidence.every(ev => scenario.message.includes(ev.quote))).toBe(true);
    }
    expect(fixture('edukasi').risk).toBe('low');
    expect(fixture('suara').checks.find(c => c.key === 'forensic')?.status).toBe('inconclusive');
  });
});
