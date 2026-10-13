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
