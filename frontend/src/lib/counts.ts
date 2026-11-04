/** One wording for progress everywhere: boss card, skill tree, branch header, node grid. */
export interface Counts {
  n_exercises: number
  n_passed: number
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

export function exercisesLabel(c: Counts): string {
  return `${c.n_passed}/${plural(c.n_exercises, 'exercise')}`
}

export function nodesLabel(c: { n_nodes: number; n_mastered: number }): string {
  return `${c.n_mastered}/${plural(c.n_nodes, 'node')} mastered`
}

export function ratio(c: Counts): number {
  return c.n_exercises ? c.n_passed / c.n_exercises : 0
}
