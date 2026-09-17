export function defaultPage(session) {
  if (!session || session.user === 'Guest') return '/store'
  if (session.platform_admin) return '/admin'
  if (session.roles?.includes('LC Shop Owner') || session.roles?.includes('LC Shop Staff')) return '/shop'
  if (session.roles?.includes('LC Delivery Person')) return '/delivery'
  return '/store'
}

export function authenticatedPage(session, path) {
  if (session?.user && session.user !== 'Guest' && ['/login', '/signup'].includes(path)) return defaultPage(session)
  return null
}

export function loginDestination(session, candidate) {
  if (typeof candidate === 'string' && /^\/(store|shop|orders|account|delivery|favourites|categories|admin|store-settings)(\/|\?|$)/.test(candidate) && candidate !== '/store') return candidate
  return defaultPage(session)
}
