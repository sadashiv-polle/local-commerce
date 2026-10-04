import test from 'node:test'
import assert from 'node:assert/strict'
import { call, setCsrfToken, upload } from '../src/api.js'

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

test('image uploads use multipart data with CSRF protection', async () => {
  setCsrfToken('upload-csrf')
  const file = new Blob(['image'], { type: 'image/png' })
  Object.defineProperty(file, 'name', { value: 'item.png' })
  globalThis.fetch = async (path, options) => {
    assert.equal(path, '/api/method/local_commerce.api.owner.upload_product_image')
    assert.equal(options.headers['X-Frappe-CSRF-Token'], 'upload-csrf')
    assert.equal(options.headers['Content-Type'], undefined)
    assert.equal(options.body.get('shop'), 'SHOP-1')
    assert.equal(options.body.get('file').name, 'item.png')
    return { ok: true, json: async () => ({ message: { image: '/files/item.png' } }) }
  }
  assert.deepEqual(await upload('owner.upload_product_image', { shop: 'SHOP-1' }, file), { image: '/files/item.png' })
})

test('permission failures expose a safe message', async () => {
  globalThis.fetch = async () => ({ status: 403, ok: false })
  await assert.rejects(call('shops.get_shop', { shop: 'B' }), /do not have access/)
})

test('server errors do not expose server response', async () => {
  globalThis.fetch = async () => ({ status: 500, ok: false, json: async () => ({ exc: 'private trace' }) })
  await assert.rejects(call('shops.list_shops'), /could not be completed/)
})

test('owner validation messages are safe and preserve status for retry handling', async () => {
  globalThis.fetch = async () => ({ status: 417, ok: false, json: async () => ({ lc_message: 'Not enough stock', exc: 'private traceback' }) })
  await assert.rejects(call('owner.adjust_stock', {}, true), error => error.status === 417 && error.message === 'Not enough stock')
})

test('ordinary framework validation does not expose raw server messages', async () => {
  globalThis.fetch = async () => ({ status: 417, ok: false, json: async () => ({ _server_messages: 'private information' }) })
  await assert.rejects(call('owner.adjust_stock', {}, true), /could not be completed/)
})

test('network failures explain safe recovery without discarding pending mutations', async () => {
  globalThis.fetch = async () => { throw new TypeError('private network details') }
  await assert.rejects(call('orders.place', {}, true), error => error.status === 0 && /check whether the action completed/.test(error.message) && !error.message.includes('private'))
})

test('payment server failures warn against paying twice and hide technical details', async () => {
  globalThis.fetch = async () => ({ status: 500, ok: false, json: async () => ({ exc: 'SECRET', message: 'SECRET' }) })
  await assert.rejects(call('cashfree.checkout', {}, true), error => /before paying again/.test(error.message) && /HTTP 500/.test(error.message) && !error.message.includes('SECRET'))
})

test('CSRF errors tell the user to reload instead of requesting roles', async () => {
  globalThis.fetch = async () => ({ status: 403, ok: false, json: async () => ({ exc_type: 'CSRFTokenError' }) })
  await assert.rejects(call('shops.update_shop', {}, true), /Reload this page/)
})

test('expired links and upload limits give specific next steps', async () => {
  for (const [status, expected] of [[410, /Request a new link/], [413, /up to 5 MB/], [429, /Wait a few minutes/], [409, /record changed/]]) {
    globalThis.fetch = async () => ({ status, ok: false, json: async () => ({}) })
    await assert.rejects(call('customers.reset_password', {}, true), expected)
  }
})

test('invalid successful responses do not leak JSON parser errors', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => { throw new SyntaxError('SECRET') } })
  await assert.rejects(call('orders.place', {}, true), error => error.status === 502 && /whether your change was saved/.test(error.message) && !error.message.includes('SECRET'))
})
