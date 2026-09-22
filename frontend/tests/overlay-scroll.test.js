import test from 'node:test'
import assert from 'node:assert/strict'
import { installOverlayScrollLock } from '../src/overlay-scroll.js'

test('overlay locks background once, restores position, and cleans up on unmount', () => {
  let callback, open = false, disconnected = false
  const scrolls = []
  const old = { window: globalThis.window, document: globalThis.document, MutationObserver: globalThis.MutationObserver }
  globalThis.window = { scrollY: 340, scrollTo: position => scrolls.push(position.top) }
  globalThis.document = { body: { style: { position: '', top: '', width: '' } } }
  globalThis.MutationObserver = class { constructor(fn) { callback = fn } observe() {} disconnect() { disconnected = true } }
  try {
    const cleanup = installOverlayScrollLock({ querySelector: () => open })
    open = true; callback()
    assert.equal(document.body.style.top, '-340px')
    window.scrollY = 0; callback()
    assert.equal(document.body.style.top, '-340px')
    open = false; callback()
    assert.equal(document.body.style.position, '')
    assert.deepEqual(scrolls, [340])
    open = true; callback(); cleanup()
    assert.equal(disconnected, true)
    assert.equal(document.body.style.position, '')
  } finally { Object.assign(globalThis, old) }
})
