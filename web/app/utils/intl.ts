/** What the formatting helpers need from the translation library: a message by key, with named values. */
export type Translate = (key: string, named?: Record<string, unknown>) => string

type Unit = 'byte' | 'kilobyte' | 'megabyte' | 'gigabyte' | 'second' | 'minute' | 'hour' | 'megabyte-per-second'

/** "6.6 GB", "6,6 Go", "٦٫٦ غيغابايت": a number with its unit written the way the language writes it. */
export function withUnit(value: number, unit: string, locale: string, fractionDigits = 0): string {
  return new Intl.NumberFormat(locale, {
    style: 'unit',
    unit: unit as Unit,
    unitDisplay: 'short',
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

/** 324 -> "5 min 24 s" (in the language's own abbreviations), 40 -> "40 s". */
export function formatDuration(seconds: number | null, locale: string): string {
  if (seconds === null) return ''
  const total = Math.round(seconds)
  const m = Math.floor(total / 60)
  return m > 0
    ? `${withUnit(m, 'minute', locale)} ${withUnit(total % 60, 'second', locale)}`
    : withUnit(total, 'second', locale)
}

/** The name of a language in the language of the interface, capitalised the way a list shows it: "Spanish", "Español". */
export function languageName(code: string | null, locale: string): string {
  if (!code) return ''
  let name = code
  try {
    name = new Intl.DisplayNames(locale, { type: 'language' }).of(code) ?? code
  } catch {
    // an unknown code: show it as it is
  }
  return name.charAt(0).toLocaleUpperCase(locale) + name.slice(1)
}
