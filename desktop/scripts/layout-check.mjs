// Looks at the real packaged app at several window sizes, the way a person sees it (what is visible without
// scrolling), and measures what a screenshot cannot say: blank space beside the content, blank space under
// short pages, and anything that makes the page scroll sideways.
//   APP_BIN=/path/PostCall.app/Contents/MacOS/PostCall USER_DATA=/path/to/data-folder OUT=/path/to/out \
//     [ROUTES=/,/profile,/settings,/calls/<id>] [SIZES=900x600,1200x800] [SHOTS=1] node scripts/layout-check.mjs
// USER_DATA must be a folder the app can use (it is started with --user-data-dir). Use a copy.
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { Page, sleep } from '../../web/ui-check/cdp.mjs'

const { APP_BIN, USER_DATA, OUT } = process.env
if (!APP_BIN || !USER_DATA || !OUT) throw new Error('set APP_BIN, USER_DATA and OUT')
mkdirSync(OUT, { recursive: true })
const SIZES = (process.env.SIZES ?? '900x600,1200x800,1512x982,1920x1080,2560x1440,600x800,390x844').split(',').map(s => s.split('x').map(Number))
const CDP_PORT = 9345
// VS Code-based terminals set ELECTRON_RUN_AS_NODE, which would make Electron behave as plain Node.
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => key !== 'ELECTRON_RUN_AS_NODE'))
const app = spawn(APP_BIN, [`--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${USER_DATA}`], { stdio: 'ignore', env })
let page = null
const rows = []

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
  const calls = await (await fetch(`${apiBase}/calls`)).json()
  const routes = (process.env.ROUTES ?? `/,/profile,/settings,/new,/notices,/calls/${calls[0]?.id ?? 'none'}`).split(',')

  for (const route of routes) {
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 800, deviceScaleFactor: 1, mobile: false })
    await page.goto(`app://postcall${route}`, "document.querySelector('main h1, main h2, main p')")
    await sleep(700)
    for (const [width, height] of SIZES) {
      await page.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 })
      await sleep(250)
      const m = await page.eval(`(() => {
        const vw = innerWidth, vh = innerHeight
        const rect = el => el ? el.getBoundingClientRect() : null
        const shell = rect(document.querySelector('.shell'))
        const page = document.querySelector('.shell > main > :first-child')
        const main = rect(page) // the page's own box: a narrow page is narrower than the window area
        const footer = rect(document.querySelector('.shell > footer'))
        const grid = document.querySelector('.page-grid')
        const columns = grid ? new Set([...grid.children].map(c => Math.round(c.getBoundingClientRect().left))).size : 0
        const pane = rect(document.querySelector('.transcript-pane'))
        const details = !!document.querySelector('details > summary') && [...document.querySelectorAll('details > summary')].some(x => x.textContent.trim() === 'Transcript')
        const overflowing = [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > vw + 1 && getComputedStyle(e).position !== 'fixed').slice(0, 3).map(e => e.tagName.toLowerCase() + '.' + e.className)
        return {
          vw, vh,
          pageWidth: Math.round(document.documentElement.scrollWidth),
          sideScroll: document.documentElement.scrollWidth > vw,
          contentLeft: main ? Math.round(main.left) : null,
          contentWidth: main ? Math.round(main.width) : null,
          usedShare: main ? Math.round((main.width / vw) * 100) : null,
          pageHeight: Math.round(document.documentElement.scrollHeight),
          footerBottom: footer ? Math.round(footer.bottom) : null,
          overflowing,
          columns,
          pane: pane ? { top: Math.round(pane.top), bottom: Math.round(pane.bottom) } : null,
          transcriptDetails: details,
        }
      })()`)
      // Blank space under a short page: the footer should end where the window ends.
      m.blankBelow = m.pageHeight <= m.vh ? Math.max(0, m.vh - (m.footerBottom ?? m.pageHeight)) : 0
      rows.push({ route, width, height, size: `${width}x${height}`, ...m })
      if (process.env.SHOTS) {
        const name = `${route === '/' ? 'home' : route.replace(/^\//, '').replace(/[/]/g, '-').slice(0, 24)}-${width}x${height}.png`
        const shot = await page.send('Page.captureScreenshot', { format: 'png' }) // the visible window only
        writeFileSync(path.join(OUT, name), Buffer.from(shot.data, 'base64'))
      }
    }
  }
} finally {
  try { process.kill(app.pid, 'SIGTERM') } catch { /* gone */ }
  await sleep(2500)
}

const pad = (v, n) => String(v ?? '-').padEnd(n)
console.log([pad('route', 26), pad('window', 10), pad('content', 14), pad('used', 6), pad('columns', 9), pad('blank below', 12), pad('side scroll', 12), 'overflowing'].join(''))
for (const r of rows) {
  console.log([
    pad(r.route.length > 24 ? r.route.slice(0, 11) + '…' + r.route.slice(-12) : r.route, 26),
    pad(r.size, 10),
    pad(`${r.contentLeft}+${r.contentWidth}`, 14),
    pad(`${r.usedShare}%`, 6),
    pad(r.columns || '-', 9),
    pad(r.blankBelow ? `${r.blankBelow}px` : 'none', 12),
    pad(r.sideScroll ? `YES (${r.pageWidth})` : 'no', 12),
    r.overflowing.join(', '),
  ].join(''))
}

// ---- The rules. A page must never scroll sideways, a short page keeps its footer at the bottom of the window,
// and the width is used: wide pages fill it (up to the shell's own limit), single-column pages are centred.
const NARROW = new Set(['/new', '/notices'])
const failures = []
const fail = (r, why) => failures.push(`${r.route} at ${r.size}: ${why}`)
for (const r of rows) {
  if (r.sideScroll) fail(r, `scrolls sideways (page ${r.pageWidth}px in a ${r.vw}px window): ${r.overflowing.join(', ')}`)
  if (r.blankBelow > 40) fail(r, `${r.blankBelow}px of blank space under the footer (the page's own bottom padding is 32px)`)
  if (NARROW.has(r.route)) {
    const centred = Math.abs(r.contentLeft - (r.vw - r.contentWidth - 0) / 2) <= 2
    if (!centred) fail(r, `the single column is not centred (starts at ${r.contentLeft}px, ${r.contentWidth}px wide)`)
    if (r.contentWidth > 760) fail(r, `the text column is ${r.contentWidth}px wide, over 760px`)
  } else if (r.contentWidth < Math.min(0.85 * r.vw, 1300)) {
    fail(r, `the content is ${r.contentWidth}px wide (${r.usedShare}% of the window); it should use the width`)
  }
  if (r.columns && r.vw >= 1100 && r.columns < 2) fail(r, 'has room for two columns but shows one')
  if (r.columns > 1 && r.vw < 940) fail(r, `shows ${r.columns} columns in a ${r.vw}px window`)
  if (r.route.startsWith('/calls/')) {
    if (r.vw >= 1100 && !r.pane) fail(r, 'the transcript is not shown beside the proposal')
    if (r.vw >= 1100 && r.pane && r.pane.bottom - r.pane.top > r.vh - 32) fail(r, 'the transcript panel is taller than the window, so it cannot stay in view while scrolling')
    if (r.vw < 1100 && (r.pane || !r.transcriptDetails)) fail(r, 'a narrow window should offer the collapsible transcript, not the side panel')
  }
}
console.log(failures.length ? `\n${failures.length} problems:\n- ${failures.join('\n- ')}` : `\nAll ${rows.length} page and window combinations pass.`)
process.exitCode = failures.length ? 1 : 0
