import Editor, { type OnMount } from '@monaco-editor/react'
import { useLayoutEffect, useRef } from 'react'

import { monaco } from '../../lib/monaco'

interface Props {
  value: string
  onChange: (v: string) => void
  onRun: () => void
  onSubmit: () => void
}

export function SqlEditor({ value, onChange, onRun, onSubmit }: Props) {
  // Monaco commands are registered once on mount; refs keep them pointing at the latest
  // callbacks without re-registering (which would stack duplicate bindings).
  const runRef = useRef(onRun)
  const submitRef = useRef(onSubmit)
  useLayoutEffect(() => {
    runRef.current = onRun
    submitRef.current = onSubmit
  })

  const onMount: OnMount = (editor) => {
    const { KeyMod, KeyCode } = monaco
    editor.addCommand(KeyMod.CtrlCmd | KeyCode.Enter, () => runRef.current())
    editor.addCommand(KeyMod.CtrlCmd | KeyMod.Shift | KeyCode.Enter, () => submitRef.current())
    editor.focus()
  }

  return (
    <Editor
      language="sql"
      theme="alpha-desk"
      value={value}
      onChange={(v) => onChange(v ?? '')}
      onMount={onMount}
      options={{
        fontFamily: "'JetBrains Mono', ui-monospace, Menlo, monospace",
        fontSize: 13,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        renderLineHighlight: 'line',
        padding: { top: 12 },
        tabSize: 2,
        automaticLayout: true,
      }}
    />
  )
}
