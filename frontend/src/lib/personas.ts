import type { Persona } from '../api/types'

export const PERSONAS: Record<Persona, { name: string; role: string; color: string }> = {
  priya: { name: 'Priya', role: 'Portfolio Manager', color: 'var(--color-amber)' },
  marcus: { name: 'Marcus', role: 'Quant Analyst', color: 'var(--color-cyan)' },
  lena: { name: 'Lena', role: 'Head of Engineering', color: 'var(--color-violet)' },
}
