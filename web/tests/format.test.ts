import { describe, expect, it } from 'vitest'
import {
  apiErrorMessage,
  draftStatusLabel,
  formatDuration,
  formatTimestamp,
  isActive,
  isDraftActive,
  languageLabel,
  statusLabel,
  uploadErrorMessage,
} from '../app/utils/format'

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

describe('formatDuration', () => {
  it('writes minutes and seconds', () => {
    expect(formatDuration(323.9)).toBe('5 min 24 s')
    expect(formatDuration(40)).toBe('40 s')
    expect(formatDuration(null)).toBe('')
  })
})

describe('statusLabel and isActive', () => {
  it('shows the percentage while transcribing', () => {
    expect(statusLabel({ status: 'transcribing', progress: 0.426 })).toBe('Transcribing… 43%')
  })

  it('knows which states are still running', () => {
    expect(['queued', 'converting', 'transcribing'].every(s => isActive(s as never))).toBe(true)
    expect(['done', 'failed', 'cancelled'].some(s => isActive(s as never))).toBe(false)
  })
})

describe('uploadErrorMessage', () => {
  it('uses the api detail when there is one', () => {
    expect(uploadErrorMessage(415, '{"detail":"Unsupported file type."}')).toBe('Unsupported file type.')
  })

  it('explains a network failure', () => {
    expect(uploadErrorMessage(0, '')).toContain('local engine')
  })

  it('falls back to the status code', () => {
    expect(uploadErrorMessage(500, 'oops')).toBe('The upload failed (error 500).')
  })
})

describe('draft progress labels', () => {
  it('says which part of the call is being read', () => {
    expect(draftStatusLabel({ status: 'extracting', stage_detail: '2/5' })).toBe('Reading the call (part 2 of 5)')
    expect(draftStatusLabel({ status: 'extracting', stage_detail: '1/1' })).toBe('Reading the call')
    expect(draftStatusLabel({ status: 'extracting', stage_detail: null })).toBe('Reading the call')
  })

  it('labels the other states', () => {
    expect(draftStatusLabel({ status: 'drafting', stage_detail: null })).toBe('Writing the proposal')
    expect(draftStatusLabel({ status: 'queued', stage_detail: null })).toBe('Waiting to start')
    expect(['queued', 'extracting', 'drafting'].every(s => isDraftActive(s as never))).toBe(true)
    expect(['done', 'failed', 'cancelled'].some(s => isDraftActive(s as never))).toBe(false)
  })
})

describe('languageLabel and apiErrorMessage', () => {
  it('names known languages and passes others through', () => {
    expect(languageLabel('es')).toBe('Spanish')
    expect(languageLabel('ja')).toBe('ja')
    expect(languageLabel(null)).toBe('')
  })

  it('reads the api detail or falls back', () => {
    expect(apiErrorMessage({ data: { detail: 'Set up your profile first.' } }, 'x')).toBe('Set up your profile first.')
    expect(apiErrorMessage(new Error('boom'), 'fallback')).toBe('fallback')
    expect(apiErrorMessage(null, 'fallback')).toBe('fallback')
  })
})
