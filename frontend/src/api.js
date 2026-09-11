import { loginUrl } from './cart.js'
let csrfToken = ''
export function setCsrfToken(token) { csrfToken = token }
async function result(response) {
  if (response.status === 401) { window.location.assign(loginUrl(window.location.hash.slice(1))); throw new Error('Please sign in again.') }
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
export async function call(method, args = {}, mutate = false) {
  const path = `/api/method/local_commerce.api.${method}`
  const response = await fetch(mutate ? path : `${path}?${new URLSearchParams(args)}`, {
    method: mutate ? 'POST' : 'GET', credentials: 'same-origin',
    headers: mutate ? { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken } : {},
    ...(mutate ? { body: JSON.stringify(args) } : {}),
  })
  return result(response)
}
export async function upload(method, args, file) {
  const body = new FormData()
  for (const [key, value] of Object.entries(args)) body.append(key, String(value))
  body.append('file', file, file.name)
  const response = await fetch(`/api/method/local_commerce.api.${method}`, {
    method: 'POST', credentials: 'same-origin',
    headers: { 'X-Frappe-CSRF-Token': csrfToken }, body,
  })
  return result(response)
}

// Native authentication endpoint: credentials stay in memory and never enter storage.
export async function authenticate(args) {
  const response = await fetch('/api/method/login', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken },
    body: JSON.stringify(args),
  })
  if (!response.ok) throw new Error(response.status === 429 ? 'Too many attempts. Please try again later.' : response.status === 401 ? 'Login failed. Check your credentials or verification code.' : 'Login is unavailable. Please retry or contact the store.')
  const data = await response.json()
  if (data.verification && data.tmp_id) return { verification: data.verification, tmp_id: data.tmp_id }
  if (['Logged In', 'No App'].includes(data.message)) return { authenticated: true }
  if (data.message === 'Password Reset') throw new Error('Your password must be reset. Use Forgot password below.')
  throw new Error('Login could not be confirmed. Please try again.')
}
