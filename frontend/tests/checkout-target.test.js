import test from 'node:test'
import assert from 'node:assert/strict'
import { checkoutTarget } from '../src/checkout-target.js'
test('installed iOS and standalone Android use redirect checkout', () => {
  assert.equal(checkoutTarget({ navigator: { standalone: true } }), '_self')
  assert.equal(checkoutTarget({ navigator: {}, matchMedia: () => ({ matches: true }) }), '_self')
})
test('regular browsers keep modal checkout', () => {
  assert.equal(checkoutTarget({ navigator: {}, matchMedia: () => ({ matches: false }) }), '_modal')
})
