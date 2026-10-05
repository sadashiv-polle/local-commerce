import test from 'node:test'
import assert from 'node:assert/strict'
import { createCashfreeLoader } from '../src/cashfree-sdk.js'
function setup() {
  const browser = {}, scripts = []
  const document = { createElement: () => ({ remove() {} }), head: { appendChild: script => scripts.push(script) } }
  return { browser, scripts, load: createCashfreeLoader(browser, document) }
}
test('preload and checkout share a download and reuse loaded SDK', async () => {
  const { browser, scripts, load } = setup()
  const first = load(), second = load()
  assert.equal(first, second)
  assert.equal(scripts.length, 1)
  browser.Cashfree = () => {}
  scripts[0].onload()
  assert.equal(await first, browser.Cashfree)
  assert.equal(await load(), browser.Cashfree)
  assert.equal(scripts.length, 1)
})
test('failed preload can be retried on Pay', async () => {
  const { browser, scripts, load } = setup()
  const first = load()
  scripts[0].onerror()
  await assert.rejects(first)
  const retry = load()
  assert.equal(scripts.length, 2)
  browser.Cashfree = () => {}
  scripts[1].onload()
  await retry
})
