let csrfToken = ''
export function setCsrfToken(token) { csrfToken = token }
export async function call(method, args = {}, mutate = false) {
  const path = `/api/method/local_commerce.api.${method}`
  const response = await fetch(mutate ? path : `${path}?${new URLSearchParams(args)}`, {
    method: mutate ? 'POST' : 'GET', credentials: 'same-origin',
    headers: mutate ? { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken } : {},
    ...(mutate ? { body: JSON.stringify(args) } : {}),
  })
  if (response.status === 401) { window.location.assign('/login?redirect-to=' + encodeURIComponent('/local-commerce' + window.location.hash)); throw new Error('Please sign in again.') }
  if (!response.ok) {
    let message = response.status === 403 ? 'You do not have access to this operation.' : 'The request could not be completed. Please retry or contact your administrator.'
    try {
      const body = await response.json()
      if (response.status === 417 && typeof body.lc_message === 'string') message = body.lc_message
    } catch { /* Non-JSON proxy responses use the safe generic message. */ }
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return (await response.json()).message
}
