import copy from '../../local_commerce/campaign_copy.json' with { type: 'json' }

export function campaignSuggestions(product, shop) {
  const theme = product ? copy.themes.find(row => new RegExp(row.pattern, 'i').test(product.item_group || ''))?.ideas || copy.general : copy.general
  const name = String(product?.item_name || '').trim()
  const store = String(shop || '').trim()
  return copy.actions.flatMap(action => theme.map(([title, lead]) => {
    const detail = name ? `Explore ${name} at ${store}.` : `Browse ${store}.`
    const message = `${lead}. ${detail} ${action}`
    return { title, message: message.length <= 240 ? message : `${lead}. ${action}` }
  }))
}

// History is newest first. Unused ideas come first, then least recently used.
export function orderCampaignSuggestions(ideas, history) {
  const normalize = value => String(value || '').trim().replace(/\s+/g, ' ').toLowerCase()
  return ideas.map((idea, index) => {
    const latest = history.findIndex(row => normalize(row.title) === normalize(idea.title) ||
      normalize(row.message) === normalize(idea.message))
    return { idea, index, rank: latest < 0 ? Infinity : latest }
  }).sort((a, b) => a.rank === b.rank ? a.index - b.index : b.rank - a.rank)
    .map(row => row.idea)
}
