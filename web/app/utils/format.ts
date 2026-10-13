import type { Call, CallStatus } from '~/types/api'

const ACTIVE: CallStatus[] = ['queued', 'converting', 'transcribing']

export function isActive(status: CallStatus): boolean {
  return ACTIVE.includes(status)
}

/** 65 -> "1:05", 3725 -> "1:02:05" */
export function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** 324 -> "5 min 24 s", 40 -> "40 s" */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) return ''
  const total = Math.round(seconds)
  const m = Math.floor(total / 60)
  return m > 0 ? `${m} min ${total % 60} s` : `${total} s`
}

export function statusLabel(call: Pick<Call, 'status' | 'progress'>): string {
  switch (call.status) {
    case 'queued':
      return 'Waiting to start'
    case 'converting':
      return 'Preparing the audio'
    case 'transcribing':
      return `Transcribing… ${Math.round(call.progress * 100)}%`
    case 'done':
      return 'Transcript ready'
    case 'failed':
      return 'Failed'
    case 'cancelled':
      return 'Cancelled'
  }
}

/** Plain-language message for a failed upload request. */
export function uploadErrorMessage(status: number, body: string): string {
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
  } catch {
    // not JSON: fall through to the generic message
  }
  return status === 0
    ? 'Could not reach the local engine. Is the app still running?'
    : `The upload failed (error ${status}).`
}
