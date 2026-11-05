import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref, nextTick } from 'vue'

const source = readFileSync(new URL('../src/CustomerShop.vue', import.meta.url), 'utf8')
const body = source.match(/async function openProduct\(item\) \{([\s\S]*?)\n\}/)[1]
function setup() {
  const selectedProduct = ref(null), selectedPhoto = ref(2)
  let opened = 0
  const productDialog = ref({ open: false, showModal() { this.open = true; opened++ } })
  const open = new Function('selectedProduct', 'selectedPhoto', 'productDialog', 'photoViewport', 'nextTick', `return async function(item) {${body}}`)(selectedProduct, selectedPhoto, productDialog, ref(null), nextTick)
  return { open, selectedProduct, productDialog, count: () => opened }
}
test('notification API product opens and can open again after closing', async () => {
  const state = setup()
  await state.open({ item: 'fish-pack' })
  assert.equal(state.count(), 1)
  state.productDialog.value.open = false
  await state.open({ item: 'fish-pack' })
  assert.equal(state.count(), 2)
})
test('superseded product selection does not open a stale dialog', async () => {
  const state = setup()
  const pending = state.open({ item: 'fish-pack' })
  state.selectedProduct.value = null
  await pending
  assert.equal(state.count(), 0)
})
