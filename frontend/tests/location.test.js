import test from 'node:test'
import assert from 'node:assert/strict'
import { distanceKm } from '../src/location.js'

test('checkout distance matches the server great-circle estimate', () => {
  const distance = distanceKm(
    { latitude: 15.4909, longitude: 73.8278 },
    { latitude: 15.4989, longitude: 73.8278 },
  )
  assert.ok(Math.abs(distance - 0.89) < 0.01)
})

test('checkout distance is unavailable until both pins are complete', () => {
  assert.equal(distanceKm({ latitude: 15.49, longitude: 73.82 }, { latitude: '', longitude: 73.83 }), null)
})
