import test from 'node:test'
import assert from 'node:assert/strict'
import { acceptanceBlock, requestedOrderMessage } from '../src/orderAcceptance.js'

test('unpaid Cashfree explains the block and does not blame shop confirmation', () => {
  const order = { payment_method: 'Cashfree', payment_status: 'Pending' }
  assert.ok(acceptanceBlock(order))
  assert.equal(requestedOrderMessage(order), 'Waiting for payment confirmation')
})
test('verified payment still waits for accounting before acceptance', () => {
  const order = { payment_method: 'Cashfree', payment_status: 'Paid', accounting_pending: true }
  assert.match(acceptanceBlock(order), /accounting/)
  assert.equal(requestedOrderMessage(order), 'Payment verification is being completed')
})
test('paid Cashfree and unpaid COD or manual UPI allow shop acceptance', () => {
  for (const order of [
    { payment_method: 'Cashfree', payment_status: 'Paid' },
    { payment_method: 'Cash on Delivery', payment_status: 'Pending' },
    { payment_method: 'Manual UPI', payment_status: 'Pending' },
  ]) {
    assert.equal(acceptanceBlock(order), '')
    assert.equal(requestedOrderMessage(order), 'Waiting for shop confirmation')
  }
})
