// Mirrors backend/app/schemas.py. Kept in sync by hand; codegen from OpenAPI later.

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

export interface Streak {
  current: number
  best: number
  freezes: number
  max_freezes: number
  active_today: boolean
  next_milestone: number
}

export interface QuestItem {
  position: number
  slug: string
  title: string
  type: Exercise['type']
  persona: Persona
  difficulty: number
  branch_id: string
  branch_title: string
  node_title: string
  minutes: number
  completed: boolean
}

export interface QuestBoard {
  day: string // ISO date, player-local
  items: QuestItem[]
  xp_per_quest: number
  all_done_bonus: number
  done: boolean
  est_minutes: number
}

export interface Progress {
  xp_total: number
  level: Level | null
  streak: Streak | null // null until TODO(me) M2-1
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
  type: 'sql' | 'quiz' | 'python' | 'review'
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
  visible_tests: string // python only
  packages: string[]
  timeout_s: number
}

export interface ResultSet {
  columns: string[]
  rows: Cell[][]
}

export interface AttemptIn {
  code: string
  result?: ResultSet
  choice?: number
  tests?: { name: string; passed: boolean }[]
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
  quest_position: number | null
  quest_xp: number
  quests_all_done: boolean
  streak_xp: number
  streak: Streak | null
}
