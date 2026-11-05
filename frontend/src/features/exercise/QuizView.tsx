import { useEffect } from 'react'

import { InlineMarkdown } from '../../lib/markdown'

interface Props {
  choices: string[]
  selected: number | null
  onSelect: (i: number) => void
  locked: boolean
}

/** Keys 1–n select a choice; works well on mobile (spec §9: quizzes must). */
export function QuizView({ choices, selected, onSelect, locked }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const n = Number(e.key)
      if (!locked && Number.isInteger(n) && n >= 1 && n <= choices.length) onSelect(n - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [choices.length, locked, onSelect])

  return (
    <ol className="space-y-2" role="radiogroup">
      {choices.map((c, i) => (
        <li key={i}>
          <button
            role="radio"
            aria-checked={selected === i}
            disabled={locked}
            onClick={() => onSelect(i)}
            className={`flex w-full items-start gap-3 rounded border px-3 py-3 text-left text-sm transition-colors ${
              selected === i
                ? 'border-amber bg-amber/10'
                : 'border-line bg-panel hover:border-muted'
            } disabled:opacity-70`}
          >
            <span className="font-mono text-xs text-muted">{i + 1}</span>
            <InlineMarkdown text={c} />
          </button>
        </li>
      ))}
    </ol>
  )
}
