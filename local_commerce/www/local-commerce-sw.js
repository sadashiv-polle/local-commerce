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
  const url = new URL(event.notification.data?.url || '/local-commerce', self.location.origin).href
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windows => {
    const existing = windows.find(window => window.url.startsWith(self.location.origin))
    if (existing) { existing.navigate(url); return existing.focus() }
    return clients.openWindow(url)
  }))
})

