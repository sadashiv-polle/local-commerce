import test from 'node:test'
import assert from 'node:assert/strict'
import { defaultPage, loginDestination } from '../src/navigation.js'
const session = roles => ({ user: 'person@example.com', roles })
test('owners and riders open their role workspace by default', () => {
  assert.equal(defaultPage(session(['LC Shop Owner'])), '/shop')
  assert.equal(loginDestination(session(['LC Shop Owner']), '/store'), '/shop')
  assert.equal(defaultPage(session(['LC Delivery Person'])), '/delivery')
  assert.equal(loginDestination(session(['LC Delivery Person']), undefined), '/delivery')
})
test('customer checkout and explicit deep links survive login', () => {
  assert.equal(loginDestination(session(['LC Customer']), '/store/fish?cart=1'), '/store/fish?cart=1')
  assert.equal(loginDestination(session(['LC Delivery Person']), '/delivery?order=123'), '/delivery?order=123')
  assert.equal(defaultPage({ user: 'Guest', roles: [] }), '/store')
  assert.equal(defaultPage(session(['LC Customer'])), '/store')
})
test('unsafe destinations fall back to the role default', () => {
  assert.equal(loginDestination(session(['LC Delivery Person']), '//example.com'), '/delivery')
  assert.equal(loginDestination(session(['LC Shop Owner']), 'https://example.com'), '/shop')
})
