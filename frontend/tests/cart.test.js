import test from 'node:test'
import assert from 'node:assert/strict'
import { readCart, writeCart, clearCart, loginUrl, changeQuantity, activeCart, cartKey } from '../src/cart.js'
function storage() {
  const values = new Map()
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
}
const cart = { fish: { item: 'fish', item_name: 'Fresh fish', quantity: 2, rate: 100 } }
test('different selling options survive login and share one stock pool', () => {
  const product = { item: 'fish', item_name: 'Mackerel', rate: 150, available: 4, stock_available: 2, stock_per_pack: 0.5, option_id: 'seven' }
  const weight = { ...product, option_id: 'kg', stock_per_pack: 1, rate: 300, available: 2 }
  let rows = changeQuantity({}, product, 1)
  rows = changeQuantity(rows, weight, 1)
  assert.equal(Object.keys(rows).length, 2)
  assert.equal(rows[cartKey(product)].quantity, 1)
  assert.throws(() => changeQuantity(rows, weight, 1), /available stock/)
  const saved = storage()
  writeCart(saved, 'shop-a', rows)
  assert.deepEqual(readCart(saved, 'shop-a'), rows)
  rows = changeQuantity(rows, product, -1)
  assert.equal(Object.keys(rows).length, 1)
  assert.throws(() => changeQuantity({}, { ...product, option_id: '', selling_options: [{}] }, 1), /Choose a selling option/)
})
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
test('the latest cart is available from every app page', () => {
  const saved = storage()
  writeCart(saved, 'shop-a', cart)
  assert.deepEqual(activeCart(saved), { shop: 'shop-a', cart })
  const bread = { bread: { item: 'bread', item_name: 'Bread', quantity: 1, rate: 40 } }
  writeCart(saved, 'shop-b', bread)
  assert.deepEqual(activeCart(saved), { shop: 'shop-b', cart: bread })
  clearCart(saved, 'shop-b')
  assert.equal(activeCart(saved), null)
})
