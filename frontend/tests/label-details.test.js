import test from 'node:test'
import assert from 'node:assert/strict'
import { fetchLabelDetails } from '../src/label-details.js'
const token = 'a'.repeat(64)
test('public label fetch excludes session cookies and returns summary', async () => {
  const result = await fetchLabelDetails('order-a', token, async (url, options) => {
    assert.equal(options.credentials, 'omit')
    assert.equal(options.cache, 'no-store')
    assert.deepEqual(JSON.parse(options.body), { order: 'order-a', token })
    return { ok: true, json: async () => ({ message: { name: 'order-a' } }) }
  })
  assert.equal(result.name, 'order-a')
})
test('missing tokens and authorization failures stay on the label page', async () => {
  await assert.rejects(fetchLabelDetails('order-a', undefined, () => assert.fail('must not request')))
  await assert.rejects(fetchLabelDetails('order-a', token, async () => ({ ok: false, status: 401 })))
})
