import test from 'node:test'
import assert from 'node:assert/strict'
import { clearDeliverySelection } from '../src/address-selection.js'

test('a new login clears address choices without losing carts or pending orders', () => {
  const values = new Map([['lc-selected-address:alice', 'home'], ['lc-selected-address:bob', 'work'], ['lc-cart:shop', 'items'], ['lc-delivery:alice:shop', 'pending']])
  const storage = { get length() { return values.size }, key: i => [...values.keys()][i], removeItem: key => values.delete(key) }
  clearDeliverySelection(storage)
  assert.deepEqual([...values.keys()], ['lc-cart:shop', 'lc-delivery:alice:shop'])
  clearDeliverySelection(storage)
  assert.equal(values.size, 2)
})
