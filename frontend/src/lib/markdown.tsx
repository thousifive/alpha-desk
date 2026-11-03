import { Fragment, type ReactNode } from 'react'

/**
 * Minimal markdown for ticket prompts: paragraphs, - / 1. lists, **bold**, *em*, `code`.
 * Builds React elements (no innerHTML), so even a malformed YAML prompt can't inject markup.
 */
export function Markdown({ source }: { source: string }) {
  const blocks = source.trim().split(/\n\s*\n/)
  return (
    <div className="prose-ticket">
      {blocks.map((block, i) => {
        const lines = block.split('\n')
        if (lines.every((l) => /^\s*-\s+/.test(l))) {
          return (
            <ul key={i}>
              {lines.map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*-\s+/, ''))}</li>
              ))}
            </ul>
          )
        }
        if (lines.every((l) => /^\s*\d+\.\s+/.test(l) || /^\s{2,}\S/.test(l))) {
          const items = lines.reduce<string[]>((acc, l) => {
            if (/^\s*\d+\.\s+/.test(l)) acc.push(l.replace(/^\s*\d+\.\s+/, ''))
            else acc[acc.length - 1] += ` ${l.trim()}`
            return acc
          }, [])
          return (
            <ol key={i}>
              {items.map((t, j) => (
                <li key={j}>{inline(t)}</li>
              ))}
            </ol>
          )
        }
        return <p key={i}>{inline(lines.join(' '))}</p>
      })}
    </div>
  )
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
