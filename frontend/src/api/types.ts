// Mirrors backend/app/schemas.py. Keep in sync by hand for M1; codegen from OpenAPI later.

export type Cell = string | number | boolean | null
export type NodeState = 'locked' | 'available' | 'mastered' | 'coming_soon'
export type Persona = 'priya' | 'marcus' | 'lena'

export interface Level {
  index: number
  title: string
  min_xp: number
  next_title: string | null
  next_min_xp: number | null
}

export interface Boss {
  branch_id: string
  branch_title: string
  title: string
  description: string
}

export interface Progress {
  xp_total: number
  level: Level | null
  passed_exercises: number
  playable_exercises: number
  mastered_nodes: number
  next_boss: Boss | null
}

export interface BranchSummary {
  id: string
  title: string
  description: string
  order: number
  playable: boolean
  playable_from: string
  boss: Boss | null
  n_nodes: number
  n_mastered: number
  n_exercises: number
  n_passed: number
}

export interface ExerciseSummary {
  slug: string
  title: string
  type: string
  persona: Persona
  difficulty: number
  passed: boolean
}

export interface SkillNode {
  slug: string
  title: string
  description: string
  order: number
  prerequisites: string[]
  xp_reward: number
  state: NodeState
  exercises: ExerciseSummary[]
}

export interface BranchDetail extends BranchSummary {
  nodes: SkillNode[]
}

export interface Exercise {
  slug: string
  title: string
  type: 'sql' | 'quiz' | 'python' | 'polars' | 'review'
  persona: Persona
  difficulty: number
  prompt_md: string
  starter_code: string
  choices: string[]
  branch_id: string
  node_slug: string
  node_title: string
  node_state: NodeState
  passed: boolean
  next_slug: string | null
}

export interface ResultSet {
  columns: string[]
  rows: Cell[][]
}

export interface AttemptIn {
  code: string
  result?: ResultSet
  choice?: number
  duration_ms: number
  hints_used?: number
}

export interface AttemptOut {
  passed: boolean
  feedback: string
  explanation: string | null
  xp_awarded: number
  node_bonus_xp: number
  xp_total: number
  already_passed: boolean
  level_before: Level | null
  level_after: Level | null
}
