const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../assets/js/app.js'), 'utf8');
const start = source.indexOf('  async function runUsernameStream(');
const end = source.indexOf('  async function consumeUsernameStream(', start);

function harness(consume) {
  class GateError extends Error {}
  const sandbox = { consumeUsernameStream: consume, crypto: { randomUUID: () => 'generated-request-id' },
    AbortController, setTimeout, clearTimeout, GateError };
  vm.runInNewContext(source.slice(start, end) + '\nglobalThis.run = runUsernameStream;', sandbox);
  return sandbox;
}

test('acknowledged job reconnects to the same job without another admission', async () => {
  const calls = [];
  const jobId = 'a'.repeat(32);
  const env = harness(async (value, body, signal, resume, onJob) => {
    calls.push({ value, body, resume });
    if (!resume) { onJob(jobId); throw new Error('connection dropped'); }
  });
  await env.run('fixture', { username: 'fixture', scope: 'full' });
  assert.equal(calls.length, 2);
  assert.equal(calls[0].body.request_id, 'generated-request-id');
  assert.equal(calls[1].resume, jobId);
  assert.equal(calls[0].body, calls[1].body);
});

test('unacknowledged transport failure cannot automatically spend another allowance', async () => {
  let calls = 0;
  const env = harness(async () => { calls++; throw new Error('connection dropped'); });
  await assert.rejects(env.run('fixture', { scope: 'extended' }), /connection dropped/);
  assert.equal(calls, 1);
});

test('cancellation does not reconnect and supplied request id stays stable', async () => {
  let calls = 0;
  const env = harness(async (value, body, signal, resume, onJob) => {
    calls++;
    assert.equal(body.request_id, 'original-request-id');
    onJob('a'.repeat(32));
    const error = new Error('aborted'); error.name = 'AbortError'; throw error;
  });
  await assert.rejects(env.run('fixture', { scope: 'full', request_id: 'original-request-id' }), /time limit/);
  assert.equal(calls, 1);
});

test('account gate is returned to the user without reconnecting', async () => {
  let calls = 0;
  let env;
  env = harness(async (value, body, signal, resume, onJob) => {
    calls++; onJob('a'.repeat(32)); throw new env.GateError('sign in');
  });
  await assert.rejects(env.run('fixture', { scope: 'full' }), /sign in/);
  assert.equal(calls, 1);
});
