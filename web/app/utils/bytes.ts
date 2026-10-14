import { withUnit, type Translate } from '~/utils/intl'

/** Sizes the way download pages show them: decimal units, one decimal for GB. 7_400_000_000 -> "7.4 GB" */
export function formatBytes(bytes: number, locale = 'en'): string {
  if (bytes >= 1e9) return withUnit(bytes / 1e9, 'gigabyte', locale, 1)
  if (bytes >= 1e6) return withUnit(Math.round(bytes / 1e6), 'megabyte', locale)
  if (bytes >= 1e3) return withUnit(Math.round(bytes / 1e3), 'kilobyte', locale)
  return withUnit(Math.max(0, Math.round(bytes)), 'byte', locale)
}

/** "2.1 GB of 7.4 GB" */
export function formatProgress(completed: number, total: number, locale: string, t: Translate): string {
  return total > 0
    ? t('download.progress', { done: formatBytes(completed, locale), total: formatBytes(total, locale) })
    : formatBytes(completed, locale)
}

/** 35_200_000 -> "35 MB/s". Empty while the speed is not known yet. */
export function formatSpeed(bytesPerSecond: number | null, locale: string, t: Translate): string {
  if (bytesPerSecond === null) return ''
  if (bytesPerSecond <= 0) return t('download.waiting')
  if (bytesPerSecond >= 1e9) return withUnit(bytesPerSecond / 1e9, 'gigabyte-per-second', locale, 1)
  if (bytesPerSecond >= 1e6) return withUnit(Math.round(bytesPerSecond / 1e6), 'megabyte-per-second', locale)
  if (bytesPerSecond >= 1e3) return withUnit(Math.round(bytesPerSecond / 1e3), 'kilobyte-per-second', locale)
  return withUnit(Math.round(bytesPerSecond), 'byte-per-second', locale)
}

/** 40 -> "less than a minute left", 130 -> "about 2 min left", 5400 -> "about 1 h 30 min left" */
export function formatEta(seconds: number | null, locale: string, t: Translate): string {
  if (seconds === null || !Number.isFinite(seconds)) return ''
  if (seconds < 60) return t('eta.lessThanMinute')
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return t('eta.about', { time: withUnit(minutes, 'minute', locale) })
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  const time = rest
    ? `${withUnit(hours, 'hour', locale)} ${withUnit(rest, 'minute', locale)}`
    : withUnit(hours, 'hour', locale)
  return t('eta.about', { time })
}

export function percent(completed: number, total: number): number {
  return total > 0 ? Math.min(100, Math.floor((completed / total) * 100)) : 0
}

/** Memory sizes of a computer: 17_179_869_184 -> "16 GB" (binary, as the Mac reports it). */
export function formatMemory(bytes: number, locale = 'en'): string {
  return withUnit(Math.round(bytes / 2 ** 30), 'gigabyte', locale)
}
