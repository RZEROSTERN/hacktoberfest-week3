export type CallStatus = 'queued' | 'converting' | 'transcribing' | 'done' | 'failed' | 'cancelled'

export interface Call {
  id: string
  title: string
  created_at: string
  status: CallStatus
  /** 0 to 1, never goes backwards */
  progress: number
  error_code: string | null
  error_message: string | null
  language: string | null
  duration_s: number | null
  keep_audio: boolean
  audio_available: boolean
}

export interface TranscriptSegment {
  /** The segment id that notes and proposals cite as their source. */
  id: number
  start: number
  end: number
  text: string
}

export interface Transcript {
  call_id: string
  language: string | null
  duration_s: number | null
  segments: TranscriptSegment[]
}

export interface Profile {
  name: string
  services: string[]
  hourly_rate: string | null
  project_rates: string[]
  payment_terms: string
  /** Preferred sections in order; empty means "all, in the default order". */
  sections: string[]
  tone: string
}

export type DraftStatus = 'queued' | 'extracting' | 'drafting' | 'done' | 'failed' | 'cancelled'

/** The transcript excerpt behind an item: shown when the user clicks its source link. */
export interface Source {
  segment_id: number
  start: number
  end: number
  text: string
}

export interface DraftItem {
  text: string
  assumption: boolean
  sources: Source[]
}

export interface ProposalSection {
  id: string
  title: string
  text: string
  lines: string[]
  items: DraftItem[]
  items_label: string | null
}

export interface DraftNotes {
  client: string
  groups: Record<string, DraftItem[]>
  open_questions: string[]
}

export interface Draft {
  call_id: string
  status: DraftStatus
  /** 0 to 1, never goes backwards */
  progress: number
  /** Which part of the call is being read, e.g. "2/5" */
  stage_detail: string | null
  error_code: string | null
  error_message: string | null
  language: string
  model: string | null
  warnings: string[]
  updated_at: string
  notes: DraftNotes | null
  proposal: { language: string, sections: ProposalSection[] } | null
}

/** What the editor sends back: only the parts of each section that can be edited. */
export interface ItemEdit {
  text: string
  assumption: boolean
  segment_ids: number[]
}

export interface SectionEdit {
  id: string
  text?: string
  lines?: string[]
  items?: ItemEdit[]
}

export type SetupState = 'idle' | 'running' | 'paused' | 'failed' | 'compat_failed' | 'interrupted' | 'done'

export interface SetupStep {
  id: 'engine' | 'llm' | 'whisper' | 'verify' | 'compat' | 'ready'
  label: string
  state: 'pending' | 'running' | 'done' | 'failed'
  detail: string | null
  /** Nothing to do: it is already on this computer. */
  skipped: boolean
  completed: number
  total: number
  speed_bps: number | null
  eta_s: number | null
}

export interface SetupProgress {
  state: SetupState
  llm_model: string | null
  steps: SetupStep[]
  overall: { fraction: number, completed_bytes: number, total_bytes: number }
  error_code: string | null
  error_message: string | null
}

export interface SetupStatus {
  ready: boolean
  problem: string | null
  problem_message: string | null
  ollama_reachable: boolean
  llm: { model: string | null, state: 'not_selected' | 'missing' | 'partial' | 'ready' }
  whisper: { state: 'missing' | 'partial' | 'ready', bytes: number, expected_bytes: number }
  compat_ok: boolean
  run: { state: SetupState, llm_model: string | null, fraction: number }
}

export interface SystemInfo {
  total_ram_bytes: number
  free_disk_bytes: number
}

export interface WhisperInfo {
  id: string
  title: string
  size_bytes: number
  license: string
  note: string
  state: 'missing' | 'partial' | 'ready'
  bytes_on_disk: number
}

export interface LlmChoice {
  model: string
  title: string
  recommended: boolean
  size_bytes: number
  size_exact: boolean
  ram_gb: number
  license: string
  note: string
  not_recommended_for_this_computer: boolean
  installed: boolean
}

export interface Recommended {
  version: number
  updated: string
  system: SystemInfo
  whisper: WhisperInfo
  llm: LlmChoice[]
  margin_bytes: number
  library_url: string
}

export interface InstalledModel {
  name: string
  size_bytes: number
  cloud: boolean
  active: boolean
  compat_ok: boolean
  title: string | null
  note: string | null
  license: string | null
  recommended: boolean
}

export interface ModelsInfo {
  active_model: string | null
  llm: InstalledModel[]
  whisper: WhisperInfo
  system: SystemInfo
}
