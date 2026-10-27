import { test } from 'node:test'
import assert from 'node:assert/strict'
import { metres, segmentDistance } from '../src/journey-navigation.js'
test('a rider on a long road segment is not treated as off route', () => {
  const route = [{ latitude: 15, longitude: 73 }, { latitude: 15, longitude: 73.02 }]
  assert.ok(segmentDistance({ latitude: 15, longitude: 73.01 }, route) < 1)
  assert.ok(segmentDistance({ latitude: 15.002, longitude: 73.01 }, route) > 200)
})
test('distance handles identical points and repeated geometry', () => {
  const point = { latitude: 15, longitude: 73 }
  assert.equal(metres(point, point), 0)
  assert.equal(segmentDistance(point, [point, point]), 0)
  assert.equal(segmentDistance(point, []), Infinity)
})
