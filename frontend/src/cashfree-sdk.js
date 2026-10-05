// One shared download across order cards, with retry after a failed load.
export function createCashfreeLoader(browser, document, timeoutMs = 15000) {
  let pending
  return function load() {
    if (browser.Cashfree) return Promise.resolve(browser.Cashfree)
    if (pending) return pending
    pending = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      const finish = error => {
        clearTimeout(timer)
        script.onload = null; script.onerror = null
        if (error) { script.remove(); reject(error) }
        else resolve(browser.Cashfree)
      }
      const timer = setTimeout(() => finish(new Error('Payment checkout took too long to load. Please retry.')), timeoutMs)
      script.src = 'https://sdk.cashfree.com/js/v3/cashfree.js'
      script.async = true
      script.onload = () => finish(browser.Cashfree ? null : new Error('Payment checkout could not load. Please retry.'))
      script.onerror = () => finish(new Error('Payment checkout could not load. Please retry.'))
      document.head.appendChild(script)
    }).catch(error => { pending = undefined; throw error })
    return pending
  }
}
let loader
export function loadCashfree() {
  loader ||= createCashfreeLoader(window, document)
  return loader()
}
