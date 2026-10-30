import test from 'node:test'
import assert from 'node:assert/strict'
import { campaignSuggestions } from '../src/campaign-copy.js'

test('fish copy uses the category and keeps the selected product identity', () => {
  const ideas = campaignSuggestions({ item_name: 'Bangde - 6 Pieces Pack', item_group: 'Fish & Seafood' }, 'Daily Basket')
  assert.equal(ideas.length, 100)
  assert.equal(new Set(ideas.map(row => row.title)).size, 5)
  assert.equal(new Set(ideas.map(row => row.message)).size, 100)
  for (const row of ideas) assert.ok(row.message.includes('Bangde - 6 Pieces Pack at Daily Basket'))
  assert.match(ideas[0].title, /Fish/)
})
test('eggs in a fish shop use their own category', () => {
  const ideas = campaignSuggestions({ item_name: 'Eggs', item_group: 'Dairy & Eggs' }, 'Fish Market')
  assert.match(ideas[0].title, /Breakfast/)
  assert.ok(ideas.every(row => !/seafood|fish curry/i.test(row.message)))
})
test('all themes and long names fit the notification limits without clipped sentences', () => {
  for (const category of ['Seafood', 'Dairy', 'Vegetables', 'Meat', 'Bakery', 'Beverages', 'Groceries', 'Household']) {
    for (const name of ['Product', 'Long name '.repeat(60)]) {
      const ideas = campaignSuggestions({ item_name: name, item_group: category }, 'Shop '.repeat(30))
      for (const idea of ideas) {
        assert.ok(idea.title.length <= 80)
        assert.ok(idea.message.length <= 240)
        assert.ok(idea.message.endsWith('.'))
      }
    }
  }
})
test('unknown categories and whole shops do not assume food', () => {
  for (const product of [null, { item_name: 'Soap', item_group: 'Household' }]) {
    assert.ok(campaignSuggestions(product, 'Local Shop').every(row => !/fish|meal|kitchen|breakfast/i.test(row.message)))
  }
})

import { orderCampaignSuggestions } from '../src/campaign-copy.js'
test('saved title or message moves that idea behind unused ideas', () => {
  const ideas = campaignSuggestions({ item_name: 'Bangde', item_group: 'Fish' }, 'Shop').slice(0, 5)
  const ordered = orderCampaignSuggestions(ideas, [
    { title: '  ' + ideas[0].title.toUpperCase(), message: 'edited message' },
    { title: 'edited title', message: ideas[1].message },
  ])
  assert.deepEqual(ordered, [ideas[2], ideas[3], ideas[4], ideas[1], ideas[0]])
  assert.equal(new Set(ordered.map(row => row.title)).size, 5)
})
test('when all ideas were saved the oldest is suggested first', () => {
  const ideas = campaignSuggestions(null, 'Shop').slice(0, 5)
  assert.deepEqual(orderCampaignSuggestions(ideas, ideas), [...ideas].reverse())
})
