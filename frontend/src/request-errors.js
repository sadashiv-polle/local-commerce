// Only deliberately public application messages may pass through from the server.
export function requestError(status, method = '', mutate = false, body = {}) {
  const payment = /cashfree\.(checkout|verify)|manual_upi\.(review|verify)/.test(method)
  let message
  switch (status) {
    case 401: message = 'Your session has expired. Sign in again to continue.'; break
    case 403: message = body.exc_type === 'CSRFTokenError'
      ? 'Your session needs refreshing. Reload this page, then try again.'
      : 'You do not have access to this action. Ask the shop owner or platform administrator for access.'; break
    case 404: message = 'This item or page is no longer available. Refresh the page and select it again.'; break
    case 409: case 412: message = 'This record changed while you were working. Refresh it and check the latest details before trying again.'; break
    case 410: message = 'This link has expired or was already used. Request a new link and use the latest email.'; break
    case 413: message = 'This file is too large. Choose a smaller image, up to 5 MB, and try again.'; break
    case 429: message = 'Too many attempts in a short time. Wait a few minutes before trying again.'; break
    case 400: case 417: case 422:
      message = 'The request could not be completed. Check the required fields and entered values. If they are correct, refresh the page and try again.'; break
    case 502: case 503: case 504:
      message = 'The service is temporarily unavailable. Wait a moment, then check the latest status.'; break
    default: message = 'The request could not be completed because of a server problem.'
  }
  if (status === 417 && typeof body.lc_message === 'string' && body.lc_message.length <= 2000) {
    message = body.lc_message
  } else if (status >= 500) {
    message += payment
      ? ' Check the order’s payment status before paying again. If money was deducted, contact the shop.'
      : mutate ? ' Refresh and check whether your change was saved before submitting again.'
        : ' Refresh the page shortly. If this continues, contact the shop or administrator.'
    message += ` Error code: HTTP ${status}.`
  }
  const error = new Error(message)
  error.status = status
  return error
}

export function connectionError(mutate = false) {
  const error = new Error('Could not reach the server. Check your internet connection.' +
    (mutate ? ' Once connected, check whether the action completed before submitting again.' : ' Then try again.'))
  // Do not use a validation status: callers retain pending mutation keys for safe retries.
  error.status = 0
  return error
}
