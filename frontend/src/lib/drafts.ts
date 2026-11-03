// Per-exercise editor drafts in localStorage: a convenience only, so every access is guarded
// (private mode / blocked storage throws) and the app works the same without it.
const key = (slug: string) => `alpha-desk:draft:${slug}`

export function loadDraft(slug: string): string | null {
  try {
    return localStorage.getItem(key(slug))
  } catch {
    return null
  }
}

export function saveDraft(slug: string, code: string): void {
  try {
    localStorage.setItem(key(slug), code)
  } catch {
    /* ignore */
  }
}
