import test from 'node:test'
import assert from 'node:assert/strict'
import { checkoutTarget } from '../src/checkout-target.js'
test('installed iOS and standalone Android use popup checkout', () => {
  assert.equal(checkoutTarget({ navigator: { standalone: true } }), '_modal')
  assert.equal(checkoutTarget({ navigator: {}, matchMedia: () => ({ matches: true }) }), '_modal')
})
test('regular browsers keep modal checkout', () => {
  assert.equal(checkoutTarget({ navigator: {}, matchMedia: () => ({ matches: false }) }), '_modal')
})
