import { getMeta, setMeta } from './store'

/**
 * Ask the browser not to evict our IndexedDB under storage pressure. Safari grants it for
 * installed PWAs; elsewhere it may be denied silently. Asked once, result remembered.
 */
export async function requestPersistence(): Promise<boolean | null> {
  if (typeof navigator === 'undefined' || !navigator.storage?.persist) return null
  const known = await getMeta<boolean>('persisted')
  if (known) return true
  let granted = await navigator.storage.persisted()
  if (!granted) granted = await navigator.storage.persist()
  await setMeta('persisted', granted)
  return granted
}
