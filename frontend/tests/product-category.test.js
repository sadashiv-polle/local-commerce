import { test } from 'node:test'
import assert from 'node:assert/strict'
import { categoryDetails } from '../src/product-category.js'

test('mixed shop categories suggest appropriate stock units', () => {
  for (const [category, unit] of [['Fish', 'Kg'], ['Rice', 'Kg'], ['Dairy & Eggs', 'Nos'], ['Vegetables', 'Kg'], ['Fast Food', 'Plate'], ['Beverages', 'Glass']]) {
    assert.equal(categoryDetails(category).units[0], unit)
  }
  assert.ok(categoryDetails('Vegetables').units.includes('Bunch'))
  assert.ok(categoryDetails('Fruits').units.includes('Dozen'))
})
test('unknown categories retain generic guidance without forcing a unit', () => {
  assert.deepEqual(categoryDetails('Custom category').units, [])
  assert.deepEqual(categoryDetails(' SEAFOOD '), categoryDetails('Seafood'))
})
