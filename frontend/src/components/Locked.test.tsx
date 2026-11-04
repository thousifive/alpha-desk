import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { TODOS } from '../lib/todos'
import { Locked } from './Locked'

describe('Locked', () => {
  afterEach(cleanup)

  it('names the colleague, task, function, and file', () => {
    render(<Locked task={TODOS['M2-1']} />)
    const box = screen.getByRole('status')
    expect(box.textContent).toContain('Lena:')
    expect(box.textContent).toContain('TODO(me) M2-1')
    expect(box.textContent).toContain('compute_streak()')
    expect(box.textContent).toContain('backend/app/game/streaks.py')
  })

  it('never uses the red error color', () => {
    const { container } = render(<Locked task={TODOS['#1']} />)
    render(<Locked task={TODOS['#1']} compact />, { container })
    expect(container.innerHTML).not.toMatch(/text-down|bg-down|border-down/)
  })
})
