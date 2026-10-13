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
