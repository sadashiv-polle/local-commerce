import test from 'node:test'
import assert from 'node:assert/strict'
import { displayPrice } from '../src/product-price.js'

const fish = { rate: 300, uom: 'Kg', selling_options: [
  { kind: 'Count', quantity: 7, billing: 'Pieces', piece_price: 35, estimated_weight: 0.65 },
  { kind: 'Weight', quantity: 0.5, estimated_weight: 0.5, enabled: false },
] }
test('pieces-only cards use their piece pack price and exclude hidden weight options', () => {
  assert.deepEqual(displayPrice(fish), { rate: 245, unit: 'Choose option', from: true })
})
test('both modes show the lowest visible pack price', () => {
  const both = { ...fish, selling_options: fish.selling_options.map(row => ({ ...row, enabled: true })) }
  assert.equal(displayPrice(both).rate, 150)
  assert.deepEqual(displayPrice({ rate: 90, uom: 'Nos' }), { rate: 90, unit: 'Nos', from: false })
})
