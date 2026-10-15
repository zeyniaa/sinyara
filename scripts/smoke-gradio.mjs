import assert from 'node:assert/strict';
import { Client } from '@gradio/client';
// Start scripts/local-gradio.py first; only a reserved example domain is submitted.
const connection = await Client.connect('http://127.0.0.1:7861', { record_history: false });
const call = async (operation, payload) => {
  const response = await connection.predict('/dispatch', { operation, payload: JSON.stringify(payload) });
  const data = JSON.parse(response.data[0]);
  assert(!data.error, data.error?.message);
  return data;
};
const access = await call('createCase', { session: crypto.randomUUID(), input: { message: '', urls: ['https://example.com'] } });
try {
  const job = connection.submit('/dispatch', { operation: 'analyzeCase', payload: JSON.stringify({ access }) });
  let snapshots = 0, last;
  for await (const event of job) {
    if (event.type !== 'data') continue;
    last = JSON.parse(event.data[0]);
    assert(!last.error);
    snapshots++;
  }
  assert.equal(last.status, 'done');
  assert.equal(last.result.mode, 'real');
  assert(last.result.evidence.some(e => e.quote === 'https://example.com'));
  console.log(JSON.stringify({ transport: '@gradio/client', snapshots, status: last.status, resultMode: last.result.mode }));
} finally {
  const deleted = await call('deleteCase', { access });
  assert.equal(deleted.deleted, true);
  connection.close();
}
