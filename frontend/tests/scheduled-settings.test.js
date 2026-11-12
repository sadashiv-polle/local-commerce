import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/ScheduledDelivery.vue', import.meta.url), 'utf8')
const body = source.match(/async function load\(resetOptions = false\) \{([\s\S]*?)\n\}/)[1]
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

test('slot refresh keeps delivery option drafts; saving options reloads persisted values', async () => {
  const settings = { value: { normal: false, scheduled: true } }
  const load = new AsyncFunction('resetOptions', 'settings', 'call', 'props', 'pageStart', 'drivers', 'revision', 'error', body)
  const call = async method => method === 'scheduled.settings' ? { normal: true, scheduled: false, schedules: ['new slot'] } : []
  const args = [settings, call, { shop: 'a' }, { value: 0 }, { value: [] }, { value: 0 }, { value: '' }]
  await load(false, ...args)
  assert.equal(settings.value.normal, false)
  assert.equal(settings.value.scheduled, true)
  assert.deepEqual(settings.value.schedules, ['new slot'])
  await load(true, ...args)
  assert.equal(settings.value.normal, true)
  assert.equal(settings.value.scheduled, false)
})
