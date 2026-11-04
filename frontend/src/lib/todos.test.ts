import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { TODOS, todoFromMessage } from './todos'

const REPO = resolve(__dirname, '../../..')

describe('todoFromMessage', () => {
  it('finds the task a backend 501 names', () => {
    expect(todoFromMessage('Grader offline: TODO(me) M2-3: grade_python_report')?.fn).toBe(
      'grade_python_report',
    )
    expect(todoFromMessage('Grader offline: TODO(me) #3: compare_result_sets')?.id).toBe('#3')
  })

  it('returns null for unknown or missing ids', () => {
    expect(todoFromMessage('TODO(me) M9-9: nope')).toBeNull()
    expect(todoFromMessage('Internal Server Error')).toBeNull()
  })
})

describe('TODOS registry', () => {
  // Guards the locked-state copy against drift: each entry must point at a real function.
  it.each(Object.values(TODOS))('$id points at def $fn in $file', (t) => {
    const src = readFileSync(resolve(REPO, t.file), 'utf8')
    expect(src).toMatch(new RegExp(`def ${t.fn}\\b`))
  })
})
