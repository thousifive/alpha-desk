import { useEffect, useState } from 'react'

import { registerSchemaCompletions } from '../monaco'
import { describeSchema, getDuckDB, type LoadProgress } from './db'

export type Schema = Record<string, { name: string; type: string }[]>
type State =
  | { status: 'loading'; progress: LoadProgress | null }
  | { status: 'ready'; schema: Schema }
  | { status: 'error'; error: string }

let cachedSchema: Schema | null = null

export function useDuckDB(): State {
  const [state, setState] = useState<State>(() =>
    cachedSchema
      ? { status: 'ready', schema: cachedSchema }
      : { status: 'loading', progress: null },
  )

  useEffect(() => {
    if (cachedSchema) return
    let alive = true
    getDuckDB((progress) => alive && setState({ status: 'loading', progress }))
      .then(describeSchema)
      .then((schema) => {
        cachedSchema = schema
        registerSchemaCompletions(schema)
        if (alive) setState({ status: 'ready', schema })
      })
      .catch((e: unknown) => alive && setState({ status: 'error', error: String(e) }))
    return () => {
      alive = false
    }
  }, [])

  return state
}
