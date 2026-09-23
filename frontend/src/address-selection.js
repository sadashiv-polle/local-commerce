// Delivery choice belongs to this browser session, never the saved default address.
export function clearDeliverySelection(storage) {
  try {
    for (let i = storage.length - 1; i >= 0; i--) {
      const key = storage.key(i)
      if (key?.startsWith('lc-selected-address:')) storage.removeItem(key)
    }
  } catch { /* A blocked storage area has no reusable address selection. */ }
}
