import { describe, expect, it } from 'vitest'
import { formatDuration, formatTimestamp, isActive, statusLabel, uploadErrorMessage } from '../app/utils/format'

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
