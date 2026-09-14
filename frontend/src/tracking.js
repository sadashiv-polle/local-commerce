function key(user) { return `lc-live-delivery:${String(user || '')}` }

export function savedTracking(storage, user) {
  try { return String(storage.getItem(key(user)) || '') }
  catch { return '' }
}

export function rememberTracking(storage, user, order) {
  try { storage.setItem(key(user), String(order || '')) }
  catch { /* GPS sharing still works when device storage is unavailable. */ }
}

export function forgetTracking(storage, user) {
  try { storage.removeItem(key(user)) }
  catch { /* Nothing else is required to stop the active browser watcher. */ }
}
