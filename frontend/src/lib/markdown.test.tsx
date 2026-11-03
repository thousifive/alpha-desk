import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Markdown } from './markdown'

describe('Markdown', () => {
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
})
