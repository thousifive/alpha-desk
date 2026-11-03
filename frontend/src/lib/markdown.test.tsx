import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { InlineMarkdown, Markdown } from './markdown'

describe('Markdown', () => {
  afterEach(cleanup)

  it('renders inline code, bold, em, and lists without injecting HTML', () => {
    const { container } = render(
      <Markdown
        source={
          'Give me **10 rows** of `prices`, *please*.\n\n- one\n- two\n\n<img src=x onerror=alert(1)>'
        }
      />,
    )
    expect(container.querySelector('strong')?.textContent).toBe('10 rows')
    expect(container.querySelector('code')?.textContent).toBe('prices')
    expect(container.querySelector('em')?.textContent).toBe('please')
    expect(container.querySelectorAll('li')).toHaveLength(2)
    expect(container.querySelector('img')).toBeNull()
  })

  it('joins wrapped numbered-list continuation lines', () => {
    const { container } = render(<Markdown source={'1. first line\n   continued\n2. second'} />)
    const items = [...container.querySelectorAll('ol li')].map((li) => li.textContent)
    expect(items).toEqual(['first line continued', 'second'])
  })

  it('renders fenced code verbatim, including blank lines and markdown-ish text', () => {
    const src = 'Look:\n\n```python\ndef f(x):\n    return x * 2\n\n# **not bold**\n```\n\nDone.'
    const { container } = render(<Markdown source={src} />)
    const pre = container.querySelector('pre code')
    expect(pre?.textContent).toBe('def f(x):\n    return x * 2\n\n# **not bold**')
    expect(container.querySelector('strong')).toBeNull()
    expect([...container.querySelectorAll('p')].map((p) => p.textContent)).toEqual([
      'Look:',
      'Done.',
    ])
  })

  it('joins wrapped bullet continuation lines', () => {
    const { container } = render(<Markdown source={'- first\n  continued\n- second'} />)
    const items = [...container.querySelectorAll('ul li')].map((li) => li.textContent)
    expect(items).toEqual(['first continued', 'second'])
  })

  it('InlineMarkdown renders code spans', () => {
    const { container } = render(<InlineMarkdown text={'call `requests.get(url)`'} />)
    expect(container.querySelector('code')?.textContent).toBe('requests.get(url)')
  })
})
