import { describe, expect, it } from 'vitest'
import { formatBytes, formatEta, formatMemory, formatProgress, formatSpeed, percent } from '../app/utils/bytes'
import { translator } from './support/translator'

const t = translator('en')

describe('formatBytes', () => {
  it('uses decimal units like download pages', () => {
    expect(formatBytes(6_583_656_505)).toBe('6.6 GB')
    expect(formatBytes(574_041_195)).toBe('574 MB')
    expect(formatBytes(12_000)).toBe('12 kB')
    expect(formatBytes(512)).toBe('512 byte')
    expect(formatBytes(-5)).toBe('0 byte')
  })

  it('writes the number and the unit the way each language does', () => {
    expect(formatBytes(6_583_656_505, 'de')).toMatch(/^6,6\sGB$/) // a non-breaking space joins them
    expect(formatBytes(6_583_656_505, 'ru')).toMatch(/^6,6\s?ГБ$/)
    expect(formatBytes(6_583_656_505, 'ar')).not.toContain('GB') // Arabic names the unit in Arabic
    expect(formatBytes(574_041_195, 'ja')).toMatch(/574/)
  })
})

describe('formatProgress', () => {
  it('reads like "2.1 GB of 7.4 GB"', () => {
    expect(formatProgress(2_100_000_000, 7_400_000_000, 'en', t)).toBe('2.1 GB of 7.4 GB')
    expect(formatProgress(2_100_000_000, 0, 'en', t)).toBe('2.1 GB')
  })

  it('uses the language\'s own wording around the sizes', () => {
    expect(formatProgress(2_100_000_000, 7_400_000_000, 'es', translator('es'))).toMatch(/2,1.*7,4/)
  })
})

describe('formatSpeed', () => {
  it('shows the current speed, or says it is waiting', () => {
    expect(formatSpeed(35_200_000, 'en', t)).toBe('35 MB/s')
    expect(formatSpeed(1_500_000_000, 'en', t)).toBe('1.5 GB/s')
    expect(formatSpeed(0, 'en', t)).toBe('waiting for data…')
    expect(formatSpeed(null, 'en', t)).toBe('')
  })
})

describe('formatEta', () => {
  it('speaks in plain minutes and hours', () => {
    expect(formatEta(20, 'en', t)).toBe('less than a minute left')
    expect(formatEta(130, 'en', t)).toBe('about 2 min left')
    expect(formatEta(5400, 'en', t)).toBe('about 1 hr 30 min left')
    expect(formatEta(7200, 'en', t)).toBe('about 2 hr left')
    expect(formatEta(null, 'en', t)).toBe('')
    expect(formatEta(Infinity, 'en', t)).toBe('')
  })
})

describe('percent and formatMemory', () => {
  it('never reports more than 100 or divides by zero', () => {
    expect(percent(50, 200)).toBe(25)
    expect(percent(300, 200)).toBe(100)
    expect(percent(5, 0)).toBe(0)
  })

  it('names memory sizes the way a Mac does', () => {
    expect(formatMemory(17_179_869_184)).toBe('16 GB')
  })
})
