import test from 'node:test'
import assert from 'node:assert/strict'
import { mergeShopDrafts } from '../src/cashfreeDrafts.js'

test('refresh preserves unsaved choices, while saved shop uses server values', () => {
  const fresh = [{ name: 'a', cashfree_gateway: 'old' }, { name: 'b', cashfree_gateway: 'saved', shop_name: 'Updated' }]
  const drafts = [{ name: 'a', cashfree_gateway: 'chosen' }, { name: 'b', cashfree_gateway: 'draft' }]
  const result = mergeShopDrafts(fresh, drafts, 'b')
  assert.equal(result[0].cashfree_gateway, 'chosen')
  assert.equal(result[1].cashfree_gateway, 'saved')
  assert.equal(result[1].shop_name, 'Updated')
  assert.equal(fresh[0].cashfree_gateway, 'old')
})

test('empty selections and numeric checkboxes have explicit UI values', () => {
  const [shop] = mergeShopDrafts([{ name: 'a', cashfree_gateway: null, cashfree_enabled: '0', cashfree_auto_reconcile: 1 }])
  assert.equal(shop.cashfree_gateway, '')
  assert.equal(shop.cashfree_enabled, false)
  assert.equal(shop.cashfree_auto_reconcile, true)
  assert.equal(shop.cashfree_commission_type, 'Percentage')
})
