import test from 'node:test'
import assert from 'node:assert/strict'
import { authenticate } from '../src/api.js'

test('custom login sends credentials to native authentication endpoint', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/method/login')
    assert.equal(options.credentials, 'same-origin')
    assert.deepEqual(JSON.parse(options.body), { usr: 'test@example.test', pwd: 'test-only' })
    return { ok: true, json: async () => ({ message: 'Logged In' }) }
  }
  assert.deepEqual(await authenticate({ usr: 'test@example.test', pwd: 'test-only' }), { authenticated: true })
})
test('two-factor challenge is not treated as authenticated', async () => {
  const response = { verification: { method: 'OTP App', setup: true }, tmp_id: 'challenge' }
  globalThis.fetch = async () => ({ ok: true, json: async () => response })
  assert.deepEqual(await authenticate({}), response)
})
test('invalid login does not redirect or expose raw server errors', async () => {
  globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({ exc: 'private' }) })
  await assert.rejects(authenticate({}), /Login failed/)
})
test('unknown successful HTTP response is not treated as login success', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ message: 'Unexpected' }) })
  await assert.rejects(authenticate({}), /could not be confirmed/)
})
