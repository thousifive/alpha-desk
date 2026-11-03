import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor/editor/editor.api'
import 'monaco-editor/languages/definitions/python/register'
import 'monaco-editor/languages/definitions/sql/register'
import EditorWorker from 'monaco-editor/editor/editor.worker?worker'

// @monaco-editor/react fetches Monaco from a CDN by default; point it at our bundled copy
// (core API + SQL and Python grammars only, not every language) so it works offline and stays pinned.
self.MonacoEnvironment = { getWorker: () => new EditorWorker() }
loader.config({ monaco })

monaco.editor.defineTheme('alpha-desk', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'keyword', foreground: 'f5a524' },
    { token: 'operator.sql', foreground: 'f5a524' },
    { token: 'string', foreground: '3fb950' },
    { token: 'number', foreground: '3ccbd6' },
    { token: 'comment', foreground: '6f7d8b', fontStyle: 'italic' },
    { token: 'predefined.sql', foreground: 'a78bfa' },
    { token: 'keyword.python', foreground: 'f5a524' },
    { token: 'type.identifier.python', foreground: 'a78bfa' },
  ],
  colors: {
    'editor.background': '#0e1318',
    'editor.lineHighlightBackground': '#141b22',
    'editorLineNumber.foreground': '#3a4754',
    'editorCursor.foreground': '#f5a524',
    'editor.selectionBackground': '#f5a52433',
  },
})

let completionDisposable: monaco.IDisposable | null = null

/** Table + column autocomplete from the live DuckDB schema. */
export function registerSchemaCompletions(
  schema: Record<string, { name: string; type: string }[]>,
) {
  completionDisposable?.dispose()
  completionDisposable = monaco.languages.registerCompletionItemProvider('sql', {
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position)
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      }
      const K = monaco.languages.CompletionItemKind
      const suggestions: monaco.languages.CompletionItem[] = []
      for (const [table, cols] of Object.entries(schema)) {
        suggestions.push({
          label: table,
          kind: K.Struct,
          insertText: table,
          range,
          detail: 'table',
        })
        for (const c of cols) {
          suggestions.push({
            label: c.name,
            kind: K.Field,
            insertText: c.name,
            range,
            detail: `${table}.${c.type}`,
          })
        }
      }
      return { suggestions }
    },
  })
}

export { monaco }
