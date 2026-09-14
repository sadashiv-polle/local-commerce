import assert from 'node:assert/strict'
import test from 'node:test'
import { forgetTracking, rememberTracking, savedTracking } from '../src/tracking.js'

function storage() {
  const values = new Map()
  return {
    getItem: key => values.get(key) || null,
    removeItem: key => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  }
}

test('active rider tracking survives reload until explicitly cleared', () => {
  const localStorage = storage()
  rememberTracking(localStorage, 'rider@example.com', 'ORDER-001')
  assert.equal(savedTracking(localStorage, 'rider@example.com'), 'ORDER-001')
  assert.equal(savedTracking(localStorage, 'another@example.com'), '')
  forgetTracking(localStorage, 'rider@example.com')
  assert.equal(savedTracking(localStorage, 'rider@example.com'), '')
})
