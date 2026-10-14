import { directionOf, htmlLang, say, type Locale } from './locale'

/** The page shown while the engines start. A data URL, so no file or network is involved. */
export function startPage(locale: Locale): string {
  return `<!doctype html><html lang="${htmlLang(locale)}" dir="${directionOf(locale)}"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>PostCall</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 16px -apple-system, system-ui, sans-serif; display: grid; place-items: center; height: 100vh; margin: 0; }
  main { text-align: center; max-width: 28rem; padding: 1rem; }
  h1 { font-size: 1.4rem; margin: 0 0 .5rem; }
  p { margin: 0; opacity: .7; }
</style>
<main><h1>${say(locale, 'splash.title')}</h1><p>${say(locale, 'splash.body')}</p></main>`
}
