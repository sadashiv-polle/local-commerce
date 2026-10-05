import test from 'node:test'
import assert from 'node:assert/strict'
import { authenticatedPage, defaultPage, loginDestination, launchDestination } from '../src/navigation.js'
const session = roles => ({ user: 'person@example.com', roles })
test('history navigation skips authentication pages only while logged in', () => {
  for (const path of ['/login', '/signup']) {
    assert.equal(authenticatedPage(session(['LC Customer']), path), '/store')
    assert.equal(authenticatedPage(session(['LC Shop Owner']), path), '/shop')
    assert.equal(authenticatedPage(session(['LC Delivery Person']), path), '/delivery')
    assert.equal(authenticatedPage({ user: 'Guest' }, path), null)
    assert.equal(authenticatedPage(null, path), null)
  }
  assert.equal(authenticatedPage(session(['LC Customer']), '/store/fish'), null)
})
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

test('platform administrators default to the master dashboard and keep explicit admin links', () => {
  const admin = { user: 'admin@example.com', platform_admin: true, roles: ['LC Platform Administrator'] }
  assert.equal(defaultPage(admin), '/admin')
  assert.equal(loginDestination(admin, '/store'), '/admin')
  assert.equal(loginDestination(admin, '/admin/inventory?shop=abc'), '/admin/inventory?shop=abc')
  assert.equal(loginDestination(admin, '/store-settings'), '/store-settings')
  assert.equal(loginDestination(admin, '//example.com/admin'), '/admin')
})

 test('work users start in their workspace even when opening a saved customer page', () => {
  for (const [role, home] of [['LC Shop Owner', '/shop'], ['LC Delivery Person', '/delivery']]) {
    const user = session([role, 'LC Customer'])
    for (const path of ['/store', '/store/fish?cart=1', '/orders', '/account', '/']) {
      assert.equal(launchDestination(user, path), home)
      assert.equal(loginDestination(user, path), home)
    }
    assert.equal(authenticatedPage(user, '/store'), null, 'in-app shopping remains accessible')
    assert.equal(launchDestination(user, home), null)
  }
  assert.equal(launchDestination(session(['LC Customer']), '/orders'), null)
  assert.equal(launchDestination({ user: 'Guest' }, '/store'), null)
})

test('label verification survives login and work-first startup', () => {
  const path = '/orders/verify/abc123'
  for (const role of ['LC Customer', 'LC Shop Owner', 'LC Delivery Person']) {
    assert.equal(launchDestination(session([role]), path), null)
    assert.equal(loginDestination(session([role]), path), path)
  }
})
