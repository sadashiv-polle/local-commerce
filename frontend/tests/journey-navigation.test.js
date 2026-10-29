import { test } from 'node:test'
import assert from 'node:assert/strict'
import { metres, segmentDistance, createRerouteGuard, travelHeading } from '../src/journey-navigation.js'
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

test('rerouting requires distinct accurate off-route fixes and a five-second cooldown', () => {
  const check = createRerouteGuard()
  const fix = timestamp => ({ timestamp, coords: { accuracy: 10 } })
  assert.equal(check(fix(1), 50, 0, 6000), false)
  assert.equal(check(fix(1), 50, 0, 7000), false)
  assert.equal(check(fix(2), 50, 4000, 7000), false)
  assert.equal(check(fix(2), 50, 4000, 9000), true)
  assert.equal(check(fix(3), 10, 0, 10000), false)
  assert.equal(check(fix(4), 50, 0, 11000), false)
})
test('GPS uncertainty does not trigger unnecessary reroutes', () => {
  const check = createRerouteGuard()
  for (let timestamp = 1; timestamp < 5; timestamp++) {
    assert.equal(check({ timestamp, coords: { accuracy: 80 } }, 90, 0, 10000), false)
  }
})

const fix = (latitude, longitude, timestamp, heading = null, speed = null) => ({ timestamp, coords: { latitude, longitude, accuracy: 5, heading, speed } })
test('navigation uses GPS heading and retains direction for stationary or repeated fixes', () => {
  const first = fix(15, 73, 1000)
  assert.equal(travelHeading(null, first), null)
  assert.equal(travelHeading(null, fix(15, 73, 1000, 90, 3)), 90)
  assert.equal(travelHeading(first, fix(15, 73, 2000, 0, 0), 90), 90)
  assert.equal(travelHeading(first, first, 359), 359)
  assert.equal(travelHeading(first, fix(15.000001, 73, 2000), 90), 90)
})
test('movement-derived headings distinguish north, east and west', () => {
  const first = fix(15, 73, 1000)
  assert.ok(travelHeading(first, fix(15.001, 73, 2000)) < 1)
  assert.ok(Math.abs(travelHeading(first, fix(15, 73.001, 2000)) - 90) < 1)
  assert.ok(Math.abs(travelHeading(first, fix(15, 72.999, 2000)) - 270) < 1)
})
