import { useI18n } from 'vue-i18n'
import { LOCALE_STORAGE_KEY, LOCALES, isLocale, localeInfo, type LocaleCode } from '~/i18n/locales'

/** The current interface language, and a way to change it (remembered for the next start). */
export function useLocale() {
  const { locale } = useI18n({ useScope: 'global' })
  const { $loadLocale, $applyLocale } = useNuxtApp()

  const code = computed(() => (isLocale(locale.value) ? locale.value : 'en'))
  const direction = computed(() => localeInfo(code.value).dir)

  async function setLocale(next: LocaleCode) {
    await $loadLocale(next)
    locale.value = next
    $applyLocale(next)
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, next)
    } catch {
      // not remembered, but the language still changed
    }
  }

  return { code, direction, locales: LOCALES, setLocale }
}
