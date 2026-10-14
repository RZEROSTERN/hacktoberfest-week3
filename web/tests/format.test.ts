import { describe, expect, it } from 'vitest'
import {
  canExportPdf,
  draftStatusLabel,
  formatTimestamp,
  isActive,
  isDraftActive,
  PDF_LANGUAGES,
  PROPOSAL_LANGUAGES,
  statusLabel,
} from '../app/utils/format'
import { translator } from './support/translator'

const t = translator('en')

describe('formatTimestamp', () => {
  it('formats minutes and seconds', () => {
    expect(formatTimestamp(0)).toBe('0:00')
    expect(formatTimestamp(65.9)).toBe('1:05')
    expect(formatTimestamp(754)).toBe('12:34')
  })

  it('adds hours past one hour', () => {
    expect(formatTimestamp(3725)).toBe('1:02:05')
  })

  it('never goes negative', () => {
    expect(formatTimestamp(-3)).toBe('0:00')
  })
})

describe('statusLabel and isActive', () => {
  it('shows the percentage while transcribing', () => {
    expect(statusLabel({ status: 'transcribing', progress: 0.426 }, t)).toBe('Transcribing… 43%')
    expect(statusLabel({ status: 'done', progress: 1 }, t)).toBe('Transcript ready')
  })

  it('knows which states are still running', () => {
    expect(['queued', 'converting', 'transcribing'].every(s => isActive(s as never))).toBe(true)
    expect(['done', 'failed', 'cancelled'].some(s => isActive(s as never))).toBe(false)
  })
})

describe('draft progress labels', () => {
  it('says which part of the call is being read', () => {
    expect(draftStatusLabel({ status: 'extracting', stage_detail: '2/5' }, t)).toBe('Reading the call (part 2 of 5)')
    expect(draftStatusLabel({ status: 'extracting', stage_detail: '1/1' }, t)).toBe('Reading the call')
    expect(draftStatusLabel({ status: 'extracting', stage_detail: null }, t)).toBe('Reading the call')
  })

  it('labels the other states', () => {
    expect(draftStatusLabel({ status: 'drafting', stage_detail: null }, t)).toBe('Writing the proposal')
    expect(draftStatusLabel({ status: 'queued', stage_detail: null }, t)).toBe('Waiting to start')
    expect(['queued', 'extracting', 'drafting'].every(s => isDraftActive(s as never))).toBe(true)
    expect(['done', 'failed', 'cancelled'].some(s => isDraftActive(s as never))).toBe(false)
  })
})

describe('proposal languages', () => {
  it('offers all eleven languages, and the PDF only for the ones its font can draw', () => {
    expect([...PROPOSAL_LANGUAGES].sort()).toEqual(['ar', 'de', 'en', 'es', 'fr', 'hi', 'it', 'ja', 'pt', 'ru', 'zh'])
    expect([...PDF_LANGUAGES].sort()).toEqual(['de', 'en', 'es', 'fr', 'it', 'pt'])
    for (const code of PDF_LANGUAGES) expect(PROPOSAL_LANGUAGES).toContain(code)
  })

  it('allows the PDF for Western European languages and when the language is not known', () => {
    expect(canExportPdf('es')).toBe(true)
    expect(canExportPdf(null)).toBe(true)
    for (const code of ['ja', 'zh', 'ru', 'hi', 'ar']) expect(canExportPdf(code), code).toBe(false)
  })
})
