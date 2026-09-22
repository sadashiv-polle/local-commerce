import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../../local_commerce/www/local-commerce-sw.js', import.meta.url), 'utf8')
async function click(windows, target = '/local-commerce#/orders?order=123') {
  const handlers = {}, opened = []
  vm.runInNewContext(source, { URL, self: { location: { origin: 'https://local.test' }, addEventListener: (name, fn) => { handlers[name] = fn } }, clients: { matchAll: async () => windows, openWindow: async url => opened.push(url) } })
  let pending
  handlers.notificationclick({ notification: { data: { url: target }, close() {} }, waitUntil(promise) { pending = promise } })
  await pending
  return opened
}
test('notification uses in-app navigation without reloading an existing app', async () => {
  const messages = []; let focused = false
  const opened = await click([{ url: 'https://local.test/local-commerce#/store', postMessage: data => messages.push(data), focus: async () => { focused = true } }])
  assert.equal(opened.length, 0)
  assert.equal(messages[0].path, '/orders?order=123')
  assert.equal(focused, true)
})
test('cold notification launch seeds a return path and never hijacks Desk', async () => {
  const opened = await click([{ url: 'https://local.test/app' }])
  const url = new URL(opened[0])
  assert.equal(url.searchParams.get('notification'), '1')
  assert.equal(url.hash, '#/orders?order=123')
})
test('notification cannot navigate to another origin', async () => {
  assert.deepEqual(await click([], 'https://other.test/local-commerce'), [])
})
