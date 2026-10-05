// Public labels must never invoke the application's login redirect or session APIs.
export async function fetchLabelDetails(order, token, request = fetch) {
  if (typeof token !== 'string' || !/^[a-f0-9]{64}$/.test(token)) throw new Error('Invalid label link')
  const response = await request('/api/method/local_commerce.api.orders.label_details', {
    method: 'POST',
    credentials: 'omit',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ order, token }),
  })
  if (!response.ok) throw new Error('Label unavailable')
  const data = await response.json()
  if (!data.message?.name) throw new Error('Label unavailable')
  return data.message
}
