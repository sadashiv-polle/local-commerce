import test from 'node:test'
import assert from 'node:assert/strict'
import { reconcileOrders } from '../src/orderUpdates.js'

test('unchanged polls preserve the cards and nested data references', () => {
  const current = [{ name: 'one', status: 'Preparing', items: [{ quantity: 2 }], map: { enabled: true } }]
  const card = current[0], items = card.items, map = card.map
  const result = reconcileOrders(current, JSON.parse(JSON.stringify(current)))
  assert.equal(result, current)
  assert.equal(result[0], card)
  assert.equal(result[0].items, items)
  assert.equal(result[0].map, map)
})

test('status and live location update without replacing the order card', () => {
  const current = [{ name: 'one', status: 'Ready', items: [{ quantity: 2 }], driver_location: null }]
  const card = current[0], items = card.items
  const result = reconcileOrders(current, [{ ...card, status: 'Out for Delivery', driver_location: { latitude: 15, longitude: 73 } }])
  assert.equal(result[0], card)
  assert.equal(result[0].items, items)
  assert.equal(result[0].status, 'Out for Delivery')
  assert.deepEqual(result[0].driver_location, { latitude: 15, longitude: 73 })
})

test('removed orders and cleared fields disappear; new orders follow server order', () => {
  const retained = { name: 'one', status: 'Requested', driver_location: { latitude: 15 } }
  const result = reconcileOrders([retained, { name: 'two' }], [{ name: 'three' }, { name: 'one', status: 'Cancelled' }])
  assert.deepEqual(result.map(order => order.name), ['three', 'one'])
  assert.equal(result[1], retained)
  assert.equal('driver_location' in result[1], false)
  assert.equal(result[1].status, 'Cancelled')
})
