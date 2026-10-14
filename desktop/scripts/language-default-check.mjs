// Starts the packaged app on a fresh data folder under different system languages and checks which language the
// interface opens in, and that a language the person picked is kept over the system one.
//   APP_BIN=/path/PostCall.app/Contents/MacOS/PostCall node scripts/language-default-check.mjs
import { spawn } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { Page, sleep } from '../../web/ui-check/cdp.mjs'

const { APP_BIN } = process.env
if (!APP_BIN) throw new Error('set APP_BIN')
const CDP_PORT = 9347
const baseEnv = Object.fromEntries(Object.entries(process.env).filter(([key]) => key !== 'ELECTRON_RUN_AS_NODE'))
const results = []
const check = (name, ok, detail = '') => results.push([ok ? 'PASS' : 'FAIL', name, detail])

/** Start the app under a system language, run `inspect(page)`, quit it. */
async function withApp(systemLanguage, userData, inspect) {
  const app = spawn(APP_BIN, [`--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${userData}`, `--lang=${systemLanguage}`], { stdio: 'ignore', env: baseEnv })
  let page = null
  try {
    for (let i = 0; i < 480 && !page; i++) { // up to two minutes: a busy machine starts slowly
      try {
        const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json()
        const target = list.find(t => t.type === 'page')
        if (target) page = await Page.connect(target.webSocketDebuggerUrl)
      } catch { /* not up yet */ }
      if (!page) await sleep(250)
    }
    await page.waitFor("location.protocol === 'app:' && document.querySelector('main h1')", 120000, 'the app')
    return await inspect(page)
  } finally {
    const gone = new Promise(resolve => app.once('exit', resolve))
    try { process.kill(app.pid, 'SIGTERM') } catch { /* gone */ }
    await Promise.race([gone, sleep(20000)]) // the next start must not meet the previous app still quitting
  }
}

const state = page => page.eval('({ lang: document.documentElement.lang, dir: document.documentElement.dir, title: document.querySelector("main h1").textContent.trim() })')

const CASES = [['ja', 'ja', 'ltr'], ['es-MX', 'es', 'ltr'], ['pt-BR', 'pt', 'ltr'], ['zh-TW', 'zh-Hans', 'ltr'], ['ar', 'ar', 'rtl'], ['ko', 'en', 'ltr'], ['en-US', 'en', 'ltr']]
let english = null
try {
  // SKIP_SYSTEM=1 runs only the last scenario.
  for (const [system, wantLang, wantDir] of process.env.SKIP_SYSTEM ? [] : CASES) {
    const userData = mkdtempSync(path.join(tmpdir(), 'postcall-lang-'))
    const s = await withApp(system, userData, state)
    if (wantLang === 'en') english = english ?? s.title
    check(`a system set to ${system} opens in ${wantLang}, ${wantDir}`, s.lang === wantLang && s.dir === wantDir, `${s.lang} ${s.dir}: ${s.title}`)
    if (wantLang !== 'en') check(`…and its first screen is not English (${system})`, s.title !== english || english === null, s.title)
  }

  // A language chosen in the app wins over the system's, and is still there after a restart.
  const userData = mkdtempSync(path.join(tmpdir(), 'postcall-lang-'))
  await withApp('ja', userData, async (page) => {
    await page.eval(`(() => { const s = document.querySelector('select.language-switcher'); s.value = 'de'; s.dispatchEvent(new Event('change')); return true })()`)
    await page.waitFor("document.documentElement.lang === 'de'", 8000, 'German')
  })
  const after = await withApp('ja', userData, state)
  check('a language picked in the app is kept over the system language after a restart', after.lang === 'de', `${after.lang}: ${after.title}`)
} catch (error) {
  results.push(['FAIL', 'script error', String(error.stack ?? error)])
} finally {
  console.log(results.map(r => r.join(' | ')).join('\n'))
  process.exitCode = results.some(r => r[0] === 'FAIL') ? 1 : 0
}
