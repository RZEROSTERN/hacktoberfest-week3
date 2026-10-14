import { createI18n } from 'vue-i18n'
import en from '~/locales/en.json'
import { DEFAULT_LOCALE, LOCALE_STORAGE_KEY, localeInfo, resolveLocale, type LocaleCode } from '~/i18n/locales'

// English is always loaded (it is the fallback for anything missing); the others load when they are chosen.
type Messages = typeof en
const loaders = import.meta.glob<{ default: Messages }>('../locales/*.json')

function remembered(): string | null {
  try {
    return localStorage.getItem(LOCALE_STORAGE_KEY)
  } catch {
    return null // storage can be blocked: the system language is used instead
  }
}

/** Tell the browser the page language and direction, so fonts, hyphenation and right-to-left layout follow. */
function applyToDocument(code: LocaleCode) {
  const info = localeInfo(code)
  document.documentElement.lang = info.htmlLang
  document.documentElement.dir = info.dir
}

export default defineNuxtPlugin(async (nuxtApp) => {
  const i18n = createI18n({
    legacy: false,
    locale: DEFAULT_LOCALE as string,
    fallbackLocale: DEFAULT_LOCALE as string,
    messages: { en } as Record<string, Messages>,
    // A missing translation falls back to English quietly; a test makes sure none is missing.
    missingWarn: false,
    fallbackWarn: false,
  })

  async function load(code: LocaleCode) {
    if (!i18n.global.availableLocales.includes(code)) {
      const loader = loaders[`../locales/${code}.json`]
      if (loader) i18n.global.setLocaleMessage(code, (await loader()).default)
    }
  }

  // The window's language comes from the system until the person picks one.
  const initial = resolveLocale([remembered(), ...navigator.languages])
  await load(initial)
  i18n.global.locale.value = initial
  applyToDocument(initial)

  nuxtApp.vueApp.use(i18n)
  return { provide: { loadLocale: load, applyLocale: applyToDocument } }
})
