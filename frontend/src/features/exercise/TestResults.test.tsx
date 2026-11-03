import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { TestResults } from './TestResults'

describe('TestResults', () => {
  afterEach(cleanup) // vitest globals are off, so RTL can't register this itself

  it('shows counts, failures, and per-test stdout', () => {
    render(
      <TestResults
        kind="hidden"
        report={{
          setup_error: null,
          setup_stdout: '',
          tests: [
            { name: 'test_ok', passed: true, duration_ms: 1, stdout: 'hello\n', error: null },
            {
              name: 'test_bad',
              passed: false,
              duration_ms: 2,
              stdout: '',
              error: 'AssertionError: assert got == 3',
            },
          ],
        }}
      />,
    )
    expect(screen.getByText('HIDDEN TESTS')).toBeTruthy()
    expect(screen.getByText('1/2 passed')).toBeTruthy()
    expect(screen.getByText('AssertionError: assert got == 3')).toBeTruthy()
    expect(screen.getByText(/hello/)).toBeTruthy()
  })

  it('shows a setup error instead of a count', () => {
    render(
      <TestResults
        kind="visible"
        report={{ setup_error: 'SyntaxError: bad', setup_stdout: '', tests: [] }}
      />,
    )
    expect(screen.getByText('SyntaxError: bad')).toBeTruthy()
    expect(screen.queryByText(/passed/)).toBeNull()
  })
})
