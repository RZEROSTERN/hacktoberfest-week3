// Takes the README screenshots from the real packaged app, using a user-data folder that already went
// through setup and holds a finished draft (the one left by scripts/full-flow.mjs).
//   APP_BIN=/path/PostCall.app/Contents/MacOS/PostCall USER_DATA=/path/to/folder OUT=docs/screenshots \
//     node scripts/screenshots.mjs
// Pictures show what the window shows without scrolling, at VIEWPORT (default 1100x720).
// Optional: SUMMARY_TEXT puts that text back as the draft's summary first.
import { spawn } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { Page, sleep } from '../../web/ui-check/cdp.mjs'

const { APP_BIN, USER_DATA, OUT } = process.env
if (!APP_BIN || !USER_DATA || !OUT) throw new Error('set APP_BIN, USER_DATA and OUT')
mkdirSync(OUT, { recursive: true })
const CDP_PORT = 9343
// VS Code-based terminals set ELECTRON_RUN_AS_NODE, which would make Electron behave as plain Node.
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => key !== 'ELECTRON_RUN_AS_NODE'))
const app = spawn(APP_BIN, [`--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${USER_DATA}`], { stdio: 'ignore', env })
let page = null

try {
  for (let i = 0; i < 160 && !page; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json()
      const target = list.find(t => t.type === 'page')
      if (target) page = await Page.connect(target.webSocketDebuggerUrl)
    } catch { /* not up yet */ }
    if (!page) await sleep(250)
  }
  if (!page) throw new Error('the app window did not appear')
  await page.waitFor("location.protocol === 'app:' && document.querySelector('main h1')", 120000, 'the app to load')
  const apiBase = JSON.parse(await page.eval('JSON.stringify(window.desktop)')).apiBase
  const [width, height] = (process.env.VIEWPORT ?? '1100x720').split('x').map(Number)
  await page.resize(width, height) // the default window size or wider shows the two-column layout
  const shot = async (name) => { await sleep(500); await page.viewportShot(path.join(OUT, `${name}.png`)); console.log('saved', name) }
  const open = async (route, ready) => page.goto(`app://postcall${route}`, `location.pathname === ${JSON.stringify(route.split('?')[0])} && (${ready})`)
  const calls = await (await fetch(`${apiBase}/calls`)).json()
  const callId = calls[0].id
  if (process.env.SUMMARY_TEXT) { // put back the model's own summary after a test edit
    const response = await fetch(`${apiBase}/calls/${callId}/draft/proposal`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sections: [{ id: 'summary', text: process.env.SUMMARY_TEXT }] }),
    })
    if (!response.ok) throw new Error(`could not restore the summary: ${response.status}`)
  }

  await open('/settings', "document.querySelector('.models li')")
  await shot('settings')

  await open(`/calls/${callId}`, "document.querySelector('[data-section=scope] .chip')")
  await page.eval("document.querySelector('[data-section=scope] .chip').click()")
  await page.waitFor("document.querySelector('[data-section=scope] .quote')", 3000, 'quote')
  // Jump to the cited moment in the transcript panel, then bring the scope section into view beside it. The
  // highlight fades after 4 seconds, so the picture is taken right away.
  await page.eval("document.querySelector('[data-section=scope] .quote .link').click()")
  await page.waitFor("document.querySelector('.transcript li.highlight')", 4000, 'the highlighted segment')
  await sleep(900)
  await page.eval("document.querySelector('[data-section=scope]').scrollIntoView({ block: 'start' }); window.scrollBy(0, -24)")
  await sleep(300)
  await page.viewportShot(path.join(OUT, 'draft.png'))
  console.log('saved draft')
  await sleep(4500) // let the transcript highlight fade
  await page.eval('window.scrollTo(0, 0)')
  await page.click('Edit proposal', 'button')
  await page.waitFor("document.querySelector('.editor')", 5000, 'editor')
  await shot('editor')
} finally {
  try { process.kill(app.pid, 'SIGTERM') } catch { /* gone */ }
  await sleep(2500)
}
