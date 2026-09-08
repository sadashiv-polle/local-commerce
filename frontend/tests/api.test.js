import test from 'node:test'
import assert from 'node:assert/strict'
import { call, setCsrfToken } from '../src/api.js'

test('mutations include Frappe CSRF and same-origin credentials', async () => {
  setCsrfToken('test-csrf')
  globalThis.fetch = async (path, options) => {
    assert.equal(path, '/api/method/local_commerce.api.shops.update_shop')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers['X-Frappe-CSRF-Token'], 'test-csrf')
    assert.equal(options.credentials, 'same-origin')
    assert.equal(JSON.parse(options.body).shop, 'A')
    return { ok: true, json: async () => ({ message: { name: 'A' } }) }
  }
  assert.deepEqual(await call('shops.update_shop', { shop: 'A' }, true), { name: 'A' })
})

test('permission failures expose a safe message', async () => {
  globalThis.fetch = async () => ({ status: 403, ok: false })
  await assert.rejects(call('shops.get_shop', { shop: 'B' }), /do not have access/)
})

test('server errors do not expose server response', async () => {
  globalThis.fetch = async () => ({ status: 500, ok: false, json: async () => ({ exc: 'private trace' }) })
  await assert.rejects(call('shops.list_shops'), /could not be completed/)
})
