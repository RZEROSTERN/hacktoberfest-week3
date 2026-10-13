import { describe, expect, it } from 'vitest'
import { formatBytes, formatEta, formatMemory, formatProgress, formatSpeed, percent } from '../app/utils/bytes'

describe('formatBytes', () => {
  it('uses decimal units like download pages', () => {
    expect(formatBytes(6_583_656_505)).toBe('6.6 GB')
    expect(formatBytes(574_041_195)).toBe('574 MB')
    expect(formatBytes(12_000)).toBe('12 KB')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(-5)).toBe('0 B')
  })
})

describe('formatProgress', () => {
  it('reads like "2.1 GB of 7.4 GB"', () => {
    expect(formatProgress(2_100_000_000, 7_400_000_000)).toBe('2.1 GB of 7.4 GB')
    expect(formatProgress(2_100_000_000, 0)).toBe('2.1 GB')
  })
})

describe('formatSpeed', () => {
  it('shows the current speed, or says it is waiting', () => {
    expect(formatSpeed(35_200_000)).toBe('35 MB/s')
    expect(formatSpeed(1_500_000_000)).toBe('1.5 GB/s')
    expect(formatSpeed(0)).toBe('waiting for data…')
    expect(formatSpeed(null)).toBe('')
  })
})

describe('formatEta', () => {
  it('speaks in plain minutes and hours', () => {
    expect(formatEta(20)).toBe('less than a minute left')
    expect(formatEta(130)).toBe('about 2 min left')
    expect(formatEta(5400)).toBe('about 1 h 30 min left')
    expect(formatEta(7200)).toBe('about 2 h left')
    expect(formatEta(null)).toBe('')
    expect(formatEta(Infinity)).toBe('')
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
