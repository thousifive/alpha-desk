/**
 * RFC 4122 v4 uuid. `crypto.randomUUID` only exists in secure contexts (HTTPS or localhost),
 * so a phone on the LAN dev URL (`http://192.168.x.x:5173`) doesn't have it.
 * `getRandomValues` works everywhere.
 */
export function uuid(
  c: Pick<Crypto, 'getRandomValues'> & Partial<Pick<Crypto, 'randomUUID'>> = crypto,
): string {
  if (typeof c.randomUUID === 'function') return c.randomUUID()
  const b = c.getRandomValues(new Uint8Array(16))
  b[6] = (b[6]! & 0x0f) | 0x40 // version 4
  b[8] = (b[8]! & 0x3f) | 0x80 // variant 10xx
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}
