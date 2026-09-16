import { ref } from 'vue'
import { call } from './api.js'
export const favouriteItems = ref(new Set())
let request, account, revision = 0
export async function loadFavourites(user) {
  if (account !== user) { account = user; request = null; favouriteItems.value = new Set() }
  const currentRevision = revision
  if (!request) request = call('favourites.ids').then(ids => {
    if (account === user && currentRevision === revision) favouriteItems.value = new Set(ids)
    return ids
  }).catch(error => { request = null; throw error })
  return request
}
export function setFavourite(item, saved) {
  revision++
  const next = new Set(favouriteItems.value)
  if (saved) next.add(item); else next.delete(item)
  favouriteItems.value = next
  request = null
}
