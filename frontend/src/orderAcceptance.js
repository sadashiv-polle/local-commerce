export function acceptanceBlock(order) {
  if (order.payment_method !== 'Cashfree') return ''
  if (order.accounting_pending) return 'Payment accounting is pending. Ask a platform administrator to review this order in Cashfree settings.'
  if (order.payment_status !== 'Paid') return 'Waiting for verified Cashfree payment. The customer can complete payment or refresh payment status from their order.'
  return ''
}

export function requestedOrderMessage(order) {
  if (order.payment_method === 'Cashfree') {
    if (order.accounting_pending) return 'Payment verification is being completed'
    if (order.payment_status !== 'Paid') return 'Waiting for payment confirmation'
  }
  return 'Waiting for shop confirmation'
}
