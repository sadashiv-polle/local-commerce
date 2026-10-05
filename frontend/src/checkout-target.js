export function checkoutTarget(browser = window) {
  return browser.navigator?.standalone === true || browser.matchMedia?.('(display-mode: standalone)').matches
    ? '_self' : '_modal'
}
