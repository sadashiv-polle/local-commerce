import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import assert from 'node:assert/strict'
const script = readFileSync(new URL('../src/GatewayPayment.vue', import.meta.url), 'utf8').split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm, '')
function setup(status) {
  const props = { order: { name: 'order', payment_status: status }, customer: true }
  let update
  const context = vm.createContext({ defineProps: () => props, defineEmits: () => () => {}, ref: value => ({ value }),
    useRoute: () => ({ path: '/orders', query: {} }), onMounted: () => {}, watch: (_, cb) => { update = cb },
    call: async () => { throw new Error('HTTP 504') } })
  vm.runInContext(script, context)
  return { props, context, update, run: code => vm.runInContext(code, context) }
}
test('timeout on an already paid order does not display a payment failure', async () => {
  const app = setup('Paid'); await app.run('refresh()')
  assert.equal(app.run('error.value'), '')
})
test('pending timeout asks for verification without claiming payment received', async () => {
  const app = setup('Pending'); await app.run('refresh()')
  assert.match(app.run('error.value'), /do not pay again/)
  assert.notEqual(app.run('verified.value'), 'Paid')
  app.props.order.payment_status = 'Paid'; app.update('Paid')
  assert.equal(app.run('error.value'), '')
  assert.equal(app.run('phase.value'), 'success')
  app.props.order.payment_status = 'Refunded'; app.update('Refunded')
  assert.equal(app.run('phase.value'), '')
})
