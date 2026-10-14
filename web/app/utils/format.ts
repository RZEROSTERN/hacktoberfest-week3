import type { Call, CallStatus, Draft, DraftStatus } from '~/types/api'
import type { Translate } from '~/utils/intl'

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

export function statusLabel(call: Pick<Call, 'status' | 'progress'>, t: Translate): string {
  if (call.status === 'transcribing') return t('status.transcribing', { percent: Math.round(call.progress * 100) })
  return t(`status.${call.status}`)
}

const DRAFT_ACTIVE: DraftStatus[] = ['queued', 'extracting', 'drafting']

export function isDraftActive(status: DraftStatus): boolean {
  return DRAFT_ACTIVE.includes(status)
}

/** "2/5" -> "Reading the call (part 2 of 5)" */
export function draftStatusLabel(draft: Pick<Draft, 'status' | 'stage_detail'>, t: Translate): string {
  if (draft.status === 'extracting') {
    const [part, total] = (draft.stage_detail ?? '').split('/')
    return part && total && total !== '1' ? t('draftStatus.extractingParts', { part, total }) : t('draftStatus.extracting')
  }
  return t(`draftStatus.${draft.status}`)
}

/** Languages a proposal can be written in. The fixed wording (titles, price sentence) is translated for all of them. */
export const PROPOSAL_LANGUAGES = ['en', 'es', 'fr', 'pt', 'ja', 'de', 'ru', 'it', 'hi', 'zh', 'ar'] as const

/** The PDF export draws Western European text only (its built-in font); the others are exported as Markdown. */
export const PDF_LANGUAGES: readonly string[] = ['en', 'es', 'fr', 'pt', 'de', 'it']

export function canExportPdf(language: string | null | undefined): boolean {
  return !language || PDF_LANGUAGES.includes(language)
}
