import test from 'node:test'
import assert from 'node:assert/strict'
import { reuseSlot, tomorrowInZone } from '../src/reuse-slot.js'
const original = { name: 'past-slot', compiled: 1, enabled: 0, title: 'Morning', capacity: 20, radius_km: 5, products: 'fish', postcodes: '403001', ordering_start: '2026-09-21 18:00:00', ordering_end: '2026-09-22 06:00:00', delivery_start: '2026-09-22 08:00:00', delivery_end: '2026-09-22 10:00:00' }
test('reuse preserves overnight ordering offsets and does not carry batch identity', () => {
  const next = reuseSlot(original, '2026-09-23')
  assert.equal(next.ordering_start, '2026-09-22T18:00')
  assert.equal(next.ordering_end, '2026-09-23T06:00')
  assert.equal(next.delivery_start, '2026-09-23T08:00')
  assert.equal(next.delivery_end, '2026-09-23T10:00')
  assert.equal(next.products, 'fish')
  assert.equal(next.enabled, 1)
  assert.equal(next.name, undefined)
  assert.equal(next.compiled, undefined)
  assert.equal(original.delivery_start, '2026-09-22 08:00:00')
})
test('reuse crosses month boundaries and validates target dates', () => {
  assert.equal(reuseSlot(original, '2026-10-01').ordering_start, '2026-09-30T18:00')
  assert.throws(() => reuseSlot(original, '2026-02-30'))
  assert.throws(() => reuseSlot(original, ''))
})
test('tomorrow is based on shop timezone, not browser timezone', () => {
  const now = new Date('2026-09-21T20:00:00Z')
  assert.equal(tomorrowInZone('Asia/Kolkata', now), '2026-09-23')
  assert.equal(tomorrowInZone('America/New_York', now), '2026-09-22')
})
