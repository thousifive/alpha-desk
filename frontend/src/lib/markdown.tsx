import { Fragment, type ReactNode } from 'react'

// A fenced block: ```lang? newline, body, closing ```. split() with one capture group puts
// code bodies at the odd indexes of the result.
const FENCE = /^```[^\n]*\n([\s\S]*?)^```[ \t]*$/m
const FENCE_ALL = new RegExp(FENCE.source, 'gm')

/**
 * Minimal markdown for ticket prompts: paragraphs, - / 1. lists (wrapped continuation
 * lines allowed), ``` fenced code, **bold**, *em*, `code`.
 * Builds React elements (no innerHTML), so even a malformed YAML prompt can't inject markup.
 */
export function Markdown({ source }: { source: string }) {
  const parts = source.trim().split(FENCE_ALL)
  return (
    <div className="prose-ticket">
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <pre key={i}>
            <code>{part.replace(/\n$/, '')}</code>
          </pre>
        ) : (
          <Fragment key={i}>{blocks(part)}</Fragment>
        ),
      )}
    </div>
  )
}

/** Inline-only markdown (code, bold, em) for short strings like quiz choices. */
export function InlineMarkdown({ text }: { text: string }) {
  return <span className="prose-ticket">{inline(text)}</span>
}

const BULLET = /^\s*-\s+/
const NUMBERED = /^\s*\d+\.\s+/
const CONTINUATION = /^\s{2,}\S/

/** List items, folding indented continuation lines into the item above. */
function listItems(lines: string[], marker: RegExp): string[] | null {
  if (!marker.test(lines[0] ?? '')) return null
  if (!lines.every((l) => marker.test(l) || CONTINUATION.test(l))) return null
  return lines.reduce<string[]>((acc, l) => {
    if (marker.test(l)) acc.push(l.replace(marker, ''))
    else acc[acc.length - 1] += ` ${l.trim()}`
    return acc
  }, [])
}

function blocks(source: string): ReactNode[] {
  const text = source.trim()
  if (!text) return []
  return text.split(/\n\s*\n/).map((block, i) => {
    const lines = block.split('\n')
    const bullets = listItems(lines, BULLET)
    if (bullets) {
      return (
        <ul key={i}>
          {bullets.map((t, j) => (
            <li key={j}>{inline(t)}</li>
          ))}
        </ul>
      )
    }
    const numbered = listItems(lines, NUMBERED)
    if (numbered) {
      return (
        <ol key={i}>
          {numbered.map((t, j) => (
            <li key={j}>{inline(t)}</li>
          ))}
        </ol>
      )
    }
    return <p key={i}>{inline(lines.join(' '))}</p>
  })
}

const TOKEN = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g

function inline(text: string): ReactNode {
  return text.split(TOKEN).map((part, i) => {
    if (part.startsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('*') && part.length > 2) return <em key={i}>{part.slice(1, -1)}</em>
    return <Fragment key={i}>{part}</Fragment>
  })
}
