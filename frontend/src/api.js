import { requestError, connectionError } from './request-errors.js'
import { loginUrl } from './cart.js'
let csrfToken = ''
export function setCsrfToken(token) { csrfToken = token }
async function send(path, options) {
  try { return await fetch(path, options) }
  catch { throw connectionError(options.method === 'POST') }
}
async function result(response, method = '', mutate = false) {
  if (response.status === 401) {
    window.location.assign(loginUrl(window.location.hash.slice(1)))
    throw requestError(401)
  }
  if (!response.ok) {
    let body = {}
    try { body = await response.json() || {} } catch { /* Proxy errors may be HTML. */ }
    throw requestError(response.status, method, mutate, body)
  }
  try { return (await response.json()).message }
  catch { throw requestError(502, method, mutate) }
}
export async function call(method, args = {}, mutate = false) {
  const path = `/api/method/local_commerce.api.${method}`
  const response = await send(mutate ? path : `${path}?${new URLSearchParams(args)}`, {
    method: mutate ? 'POST' : 'GET', credentials: 'same-origin',
    headers: mutate ? { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken } : {},
    ...(mutate ? { body: JSON.stringify(args) } : {}),
  })
  return result(response, method, mutate)
}
export async function upload(method, args, file) {
  const body = new FormData()
  for (const [key, value] of Object.entries(args)) body.append(key, String(value))
  body.append('file', file, file.name)
  const response = await send(`/api/method/local_commerce.api.${method}`, {
    method: 'POST', credentials: 'same-origin',
    headers: { 'X-Frappe-CSRF-Token': csrfToken }, body,
  })
  return result(response, method, true)
}

// Native authentication endpoint: credentials stay in memory and never enter storage.
export async function authenticate(args) {
  const response = await send('/api/method/login', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken },
    body: JSON.stringify(args),
  })
  if (!response.ok) throw response.status === 401 ? new Error('Login failed. Check your email or username and password. Use Forgot password if needed.') : requestError(response.status, 'login', true)
  let data
  try { data = await response.json() } catch { throw requestError(502, 'login', true) }
  if (data.verification && data.tmp_id) return { verification: data.verification, tmp_id: data.tmp_id }
  if (['Logged In', 'No App'].includes(data.message)) return { authenticated: true }
  if (data.message === 'Password Reset') throw new Error('Your password must be reset. Use Forgot password below.')
  throw new Error('Login could not be confirmed. Please try again.')
}
