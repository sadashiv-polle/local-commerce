import test from 'node:test'
import assert from 'node:assert/strict'
import { readCart, writeCart, clearCart, loginUrl, changeQuantity } from '../src/cart.js'
function storage() {
  const values = new Map()
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
}
const cart = { fish: { item: 'fish', item_name: 'Fresh fish', quantity: 2, rate: 100 } }
test('guest cart survives login/reload using the same shop key', () => {
  const saved = storage()
  writeCart(saved, 'shop-a', cart)
  assert.deepEqual(readCart(saved, 'shop-a'), cart)
  assert.deepEqual(readCart(saved, 'shop-b'), {})
  clearCart(saved, 'shop-a')
  assert.deepEqual(readCart(saved, 'shop-a'), {})
})
test('invalid saved quantities and malformed records are excluded', () => {
  const saved = storage()
  writeCart(saved, 'a', { ...cart, bad: { item: 'bad', item_name: 'Bad', quantity: -1, rate: 0 }, other: null })
  assert.deepEqual(readCart(saved, 'a'), cart)
})
test('login URL preserves checkout route in encoded redirect', () => {
  const path = '/store/shop%20one?checkout=1'
  assert.equal(new URLSearchParams(loginUrl(path).split('?')[1]).get('next'), path)
  assert.equal(new URLSearchParams(loginUrl('//evil.test').split('?')[1]).get('next'), '/store')
})
test('storage failures propagate instead of pretending a cart was saved', () => {
  assert.throws(() => writeCart({ setItem() { throw new Error('blocked') } }, 'a', cart), /blocked/)
})
test('cart quantity controls add, increment, and remove a line', () => {
  const item = { item: 'fish', item_name: 'Fish', rate: 100, available: 2 }
  const one = changeQuantity({}, item, 1)
  assert.equal(one.fish.quantity, 1)
  const two = changeQuantity(one, item, 1)
  assert.equal(two.fish.quantity, 2)
  assert.deepEqual(changeQuantity(one, item, -1), {})
  assert.throws(() => changeQuantity(two, item, 1), /available stock/)
})
