// Fix the page behind overlays, preserving its position on iOS as well as desktop.
export function installOverlayScrollLock(root) {
  let previous = null, scrollY = 0
  const sync = () => {
    const open = !!root?.querySelector('dialog[open], .cart-backdrop, .notification-menu[open], .incoming-order')
    if (open && !previous) {
      scrollY = window.scrollY
      previous = { position: document.body.style.position, top: document.body.style.top, width: document.body.style.width }
      Object.assign(document.body.style, { position: 'fixed', top: `-${scrollY}px`, width: '100%' })
    } else if (!open && previous) {
      Object.assign(document.body.style, previous)
      previous = null
      window.scrollTo({ top: scrollY, behavior: 'instant' })
    }
  }
  const observer = new MutationObserver(sync)
  observer.observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ['open'] })
  sync()
  return () => {
    observer.disconnect()
    if (previous) {
      Object.assign(document.body.style, previous)
      window.scrollTo({ top: scrollY, behavior: 'instant' })
    }
  }
}
