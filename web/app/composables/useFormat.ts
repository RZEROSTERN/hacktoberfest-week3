import { useI18n } from 'vue-i18n'
import { draftStatusLabel, statusLabel } from '~/utils/format'
import { formatBytes, formatEta, formatMemory, formatProgress, formatSpeed } from '~/utils/bytes'
import { formatDuration, languageName, withUnit } from '~/utils/intl'
import { modelMessageKey } from '~/utils/setup'
import type { Translate } from '~/utils/intl'

/** Every number, size, time and label the screens show, in the current language. */
export function useFormat() {
  const { t, te, locale } = useI18n({ useScope: 'global' })
  const translate: Translate = (key, named) => (named ? t(key, named) : t(key))
  const exists = (key: string) => te(key)

  return {
    t: translate,
    exists,
    locale,
    bytes: (n: number) => formatBytes(n, locale.value),
    memory: (n: number) => formatMemory(n, locale.value),
    gigabytes: (n: number) => withUnit(n, 'gigabyte', locale.value),
    /** The note of a model in this language, or the api's own text when the app has no translation for it. */
    modelNote: (model: string, fallback: string) => (exists(`${modelMessageKey(model)}.note`) ? t(`${modelMessageKey(model)}.note`) : fallback),
    progress: (done: number, total: number) => formatProgress(done, total, locale.value, translate),
    speed: (bps: number | null) => formatSpeed(bps, locale.value, translate),
    eta: (seconds: number | null) => formatEta(seconds, locale.value, translate),
    duration: (seconds: number | null) => formatDuration(seconds, locale.value),
    callStatus: (call: Parameters<typeof statusLabel>[0]) => statusLabel(call, translate),
    draftStatus: (draft: Parameters<typeof draftStatusLabel>[0]) => draftStatusLabel(draft, translate),
    language: (code: string | null) => languageName(code, locale.value),
  }
}
