import test from 'node:test'
import assert from 'node:assert/strict'
import { displayTime } from '../src/display-time.js'
test('formats noon, midnight and site timestamps without timezone shifts', () => {
  assert.equal(displayTime('13:00:00'), '1:00 PM')
  assert.equal(displayTime('00:05'), '12:05 AM')
  assert.equal(displayTime('12:00'), '12:00 PM')
  assert.equal(displayTime('2026-10-06 18:30:12.345'), '2026-10-06 6:30 PM')
  assert.equal(displayTime('2026-10-06'), '2026-10-06')
  assert.equal(displayTime(null), '')
})
