self.addEventListener('push', event => {
  let data = {}
  try { data = event.data ? event.data.json() : {} } catch { data = {} }
  event.waitUntil(self.registration.showNotification(data.title || 'Local Commerce', {
    body: data.body || 'Your order has an update.',
    icon: '/assets/local_commerce/icons/icon-192.png',
    badge: '/assets/local_commerce/icons/badge-96.png',
    tag: data.tag || 'local-commerce',
    data: { url: data.url || '/local-commerce' },
  }))
})

self.addEventListener('notificationclick', event => {
  event.notification.close()
  const url = new URL(event.notification.data?.url || '/local-commerce', self.location.origin)
  if (url.origin !== self.location.origin || url.pathname !== '/local-commerce') return
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windows => {
    const existing = windows.find(client => {
      const candidate = new URL(client.url)
      return candidate.origin === url.origin && candidate.pathname === url.pathname
    })
    if (existing) {
      existing.postMessage({ type: 'lc-open-notification', path: url.hash.slice(1) || '/store' })
      return existing.focus()
    }
    // A cold launch needs an in-app home entry underneath the order detail.
    url.searchParams.set('notification', '1')
    return clients.openWindow(url.href)
  }))
})
