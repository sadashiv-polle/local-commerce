export function pushSupported() {
  return window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

function applicationKey(value) {
  const padding = '='.repeat((4 - value.length % 4) % 4)
  const bytes = atob((value + padding).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(bytes, character => character.charCodeAt(0))
}

export async function currentSubscription() {
  if (!pushSupported()) return null
  const registration = await navigator.serviceWorker.register('/local-commerce-sw.js', { scope: '/' })
  return registration.pushManager.getSubscription()
}

export async function enablePush(publicKey) {
  if (!pushSupported()) throw new Error('Phone notifications are unavailable in this browser.')
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') throw new Error('Notification permission was not allowed.')
  const registration = await navigator.serviceWorker.register('/local-commerce-sw.js', { scope: '/' })
  const existing = await registration.pushManager.getSubscription()
  return existing || registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: applicationKey(publicKey),
  })
}

export async function disablePush() {
  const subscription = await currentSubscription()
  if (!subscription) return ''
  const endpoint = subscription.endpoint
  await subscription.unsubscribe()
  return endpoint
}
