export function defaultPage(session) {
  if (!session || session.user === 'Guest') return '/store'
  if (session.platform_admin || session.roles?.includes('LC Shop Owner') || session.roles?.includes('LC Shop Staff')) return '/shop'
  if (session.roles?.includes('LC Delivery Person')) return '/delivery'
  return '/store'
}

export function loginDestination(session, candidate) {
  if (typeof candidate === 'string' && /^\/(store|shop|orders|account|delivery)(\/|\?|$)/.test(candidate) && candidate !== '/store') return candidate
  return defaultPage(session)
}
