// The whole product inside the real desktop app, with nothing but the app itself running: first-launch
// wizard (real downloads), compatibility check, profile, upload, transcription, draft, source links, edit,
// export, and a look at the network connections the app holds. Slow (several minutes) and heavy: it
// downloads the speech model (~574 MB) and a tiny language model (~270 MB) and loads gemma4:e4b.
//
//   APP_BIN=/path/PostCall.app/Contents/MacOS/PostCall node scripts/full-flow.mjs
//
// gemma4:e4b is not downloaded again (9.6 GB): it is hard-linked from the system Ollama's model folder
// (LINK_FROM, default ~/.ollama/models) into the app's own, which only reads the system folder.
// Stop the system Ollama first so it is certain that the app uses its own.
import { execFileSync, spawn } from 'node:child_process'
import { copyFileSync, existsSync, linkSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Page, sleep } from '../../web/ui-check/cdp.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const repo = path.resolve(here, '..', '..')
const out = process.env.UI_OUT ?? path.join(repo, '.dev', 'full-flow')
mkdirSync(out, { recursive: true })
const userData = mkdtempSync(path.join(process.env.SCRATCH ?? tmpdir(), 'postcall-flow-'))
const appBin = process.env.APP_BIN
if (!appBin) throw new Error('set APP_BIN to the PostCall executable inside the installed app')
const LINK_FROM = process.env.LINK_FROM ?? path.join(homedir(), '.ollama', 'models')
const SAMPLE = path.join(repo, 'samples', 'interview.mp3')
const CDP_PORT = 9342
const GOOD = 'gemma4:e4b'
const TINY = 'smollm2:135m'
const results = []
const t0 = Date.now()
const log = (m) => console.log(`[${String(Math.round((Date.now() - t0) / 1000)).padStart(4)} s] ${m}`)
const check = (name, ok, detail = '') => {
  results.push([ok ? 'PASS' : 'FAIL', name, String(detail).replace(/\s+/g, ' ').slice(0, 170)])
  log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` | ${String(detail).replace(/\s+/g, ' ').slice(0, 120)}` : ''}`)
}

function processes() {
  const text = execFileSync('ps', ['-axo', 'pid=,ppid=,command='], { encoding: 'utf8' })
  return text.split('\n').map((l) => {
    const m = l.trim().match(/^(\d+)\s+(\d+)\s+(.*)$/)
    return m ? { pid: +m[1], ppid: +m[2], command: m[3] } : null
  }).filter(Boolean)
}
function tree(rootPid) {
  const all = processes()
  const seen = new Set([rootPid])
  for (let grew = true; grew;) {
    grew = false
    for (const p of all) if (seen.has(p.ppid) && !seen.has(p.pid)) { seen.add(p.pid); grew = true }
  }
  return all.filter(p => seen.has(p.pid))
}
const alive = (pid) => { try { process.kill(pid, 0); return true } catch { return false } }

/** Every TCP connection held by the app's processes, as "local -> remote". */
function connections(pids) {
  try {
    const text = execFileSync('lsof', ['-nP', '-iTCP', '-a', '-p', pids.join(','), '-Fn', '-FT'], { encoding: 'utf8' })
    return text.split('\n').filter(l => l.startsWith('n')).map(l => l.slice(1))
  } catch { return [] }
}

function linkModel(name, tag) {
  const rel = path.join('manifests', 'registry.ollama.ai', 'library', name, tag)
  const dst = path.join(userData, 'models', 'ollama')
  const manifest = JSON.parse(readFileSync(path.join(LINK_FROM, rel), 'utf8'))
  mkdirSync(path.join(dst, 'blobs'), { recursive: true })
  mkdirSync(path.dirname(path.join(dst, rel)), { recursive: true })
  for (const { digest } of [manifest.config, ...manifest.layers]) {
    const file = `sha256-${digest.split(':')[1]}`
    const target = path.join(dst, 'blobs', file)
    if (!existsSync(target)) linkSync(path.join(LINK_FROM, 'blobs', file), target)
  }
  copyFileSync(path.join(LINK_FROM, rel), path.join(dst, rel))
}

// VS Code-based terminals set ELECTRON_RUN_AS_NODE, which would make Electron behave as plain Node.
const cleanEnv = Object.fromEntries(Object.entries(process.env).filter(([key]) => key !== 'ELECTRON_RUN_AS_NODE'))
const shell = spawn(appBin, [`--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${userData}`], { stdio: ['ignore', 'ignore', 'ignore'], env: cleanEnv })
let page = null
let apiBase = ''
const apiJson = async p => (await fetch(`${apiBase}${p}`)).json()

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
  apiBase = JSON.parse(await page.eval('JSON.stringify(window.desktop)')).apiBase
  check('the packaged app opens by itself, with no terminal and no system Ollama', true, `api at ${apiBase}`)
  check('the system Ollama is not running during this check', await fetch('http://127.0.0.1:11434/api/version', { signal: AbortSignal.timeout(1500) }).then(() => false, () => true))
  const downloads = path.join(out, 'downloads')
  await page.allowDownloads(downloads).catch(() => {})
  await page.resize(1100, 720).catch(() => {})
  await sleep(500)

  // ---- 1. First launch: the request, with a real download of the speech model and a tiny language model
  await page.waitFor("document.body.innerText.includes('Welcome to PostCall')", 20000, 'the request screen')
  let t = await page.text()
  check('first launch asks to download the models before anything else', (await page.eval('location.pathname')) === '/setup' && /fully offline/.test(t) && /Download now/.test(t) && /Not now/.test(t))
  check('the recommended Gemma 4 model is preselected, with size and license', await page.eval(`document.querySelector('input[type=radio][value="${GOOD}"]').checked`) && /6\.6 GB download/.test(t) && /Apache 2\.0/.test(t))
  await page.viewportShot(path.join(out, '01-request.png'))

  await page.eval("document.querySelector('input[type=radio][value=__custom__]').click()")
  await page.fill('input[aria-label="Ollama model name and tag"]', TINY)
  await page.click('Download now', 'button')
  await page.waitFor("document.querySelector('[data-step=engine]')", 15000, 'the progress screen')
  log('downloading (real network): the tiny model first, then the speech model')
  let shown = false
  let last = ''
  const endAt = Date.now() + 20 * 60 * 1000
  for (;;) {
    const p = await apiJson('/setup/progress')
    const running = p.steps.find(s => s.state === 'running')
    const line = running ? `${running.id}: ${running.completed}/${running.total}` : p.state
    if (line !== last && /whisper|llm/.test(line)) log(line)
    last = line
    if (!shown && running?.id === 'whisper' && running.completed > 20e6) {
      await sleep(1500)
      const text = await page.eval("document.querySelector('[data-step=whisper] .progress span')?.textContent ?? ''")
      check('a download shows percentage, size, speed and time left', /\d+%/.test(text) && /MB of 574 MB/.test(text) && /MB\/s/.test(text) && /left/.test(text), text)
      await page.viewportShot(path.join(out, '02-downloading.png'))
      shown = true
    }
    if (['done', 'compat_failed', 'failed'].includes(p.state)) break
    if (Date.now() > endAt) throw new Error('the downloads did not finish in 20 minutes')
    await sleep(2000)
  }
  const afterTiny = await apiJson('/setup/progress')
  check('the tiny model is refused by the compatibility check, in plain language', afterTiny.state === 'compat_failed' && /too small|structured notes|writing tasks/.test(afterTiny.error_message ?? ''), afterTiny.error_message)
  await page.viewportShot(path.join(out, '03-compat-failed.png'))
  check('the app stays locked until a model passes', (await apiJson('/setup/status')).ready === false)

  // ---- 2. The recommended model: made available without the 9.6 GB download, then really checked
  linkModel('gemma4', 'e4b')
  await page.click('Use the recommended model', 'button')
  await page.waitFor("document.body.innerText.includes('Everything is ready')", 360000, 'the recommended model to pass its check')
  const ready = await apiJson('/setup/progress')
  check('Gemma 4 E4B passes the real compatibility check inside the app', ready.state === 'done' && (await apiJson('/setup/status')).ready === true)
  await page.viewportShot(path.join(out, '04-ready.png'))
  await page.click('Start using PostCall', 'button')
  await page.waitFor("document.querySelector('main h1')?.textContent.includes('Your calls')", 10000, 'home')

  // ---- 3. Profile
  await page.goto('app://postcall/profile', "location.pathname === '/profile' && document.querySelector('form')")
  const setNth = (sel, n, v) => page.eval(`(() => { const el = document.querySelectorAll(${JSON.stringify(sel)})[${n}]
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(v)}); el.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await setNth('form input[type=text]', 0, 'Ana Pérez (Studio Demo)')
  await setNth('form textarea', 0, 'Sitios web\nSistemas de reservaciones')
  await setNth('form input[type=text]', 1, '650 MXN por hora')
  await setNth('form textarea', 1, 'Sitio web de hasta 5 secciones: 24,000 MXN')
  await setNth('form textarea', 2, '50% de anticipo y 50% a la entrega.')
  await setNth('form input[type=text]', 2, 'profesional y cercano')
  await page.click('Save profile', 'button')
  await page.waitFor("document.body.innerText.includes('Profile saved.')", 8000, 'profile saved')
  check('the profile is saved', true)

  // ---- 4. Upload and transcription
  await page.goto('app://postcall/new', "location.pathname === '/new' && document.querySelector('input[type=file]')")
  check('the upload screen reminds that participants must consent to being recorded', /consent/i.test(await page.text()))
  const { root } = await page.send('DOM.getDocument')
  const { nodeId } = await page.send('DOM.querySelector', { nodeId: root.nodeId, selector: 'input[type=file]' })
  await page.send('DOM.setFileInputFiles', { nodeId, files: [SAMPLE] })
  await sleep(300)
  const transcribeStart = Date.now()
  await page.click('Start transcription', 'button')
  await page.waitFor("location.pathname.startsWith('/calls/')", 30000, 'the call page')
  const callId = await page.eval('location.pathname.split("/").pop()')
  await page.waitFor("document.querySelector('.progress progress')", 15000, 'transcription progress')
  check('transcription shows progress and can be cancelled', /Cancel/.test(await page.text()))
  await page.viewportShot(path.join(out, '05-transcribing.png'))
  await page.waitFor("document.body.innerText.includes('Proposal draft')", 600000, 'the transcript')
  const transcribeSeconds = Math.round((Date.now() - transcribeStart) / 1000)
  const call = await apiJson(`/calls/${callId}`)
  check('the 5-minute call is transcribed, language detected', call.status === 'done' && call.language === 'es', `${transcribeSeconds} s for ${Math.round(call.duration_s)} s of audio, language ${call.language}`)
  check('the audio file was deleted after transcription', !readdirSync(path.join(userData, 'data'), { recursive: true }).some(f => /\.(mp3|m4a|wav|mp4)$/i.test(String(f))) && !(await page.text()).includes('is kept on this computer'))

  // ---- 5. Draft
  const draftStart = Date.now()
  await page.click('Draft proposal', 'button')
  await page.waitFor("document.querySelector('.progress progress')", 10000, 'draft progress')
  await page.viewportShot(path.join(out, '06-drafting.png'))
  await page.waitFor("document.querySelector('[data-section=scope]')", 420000, 'the draft')
  const draftSeconds = Math.round((Date.now() - draftStart) / 1000)
  await sleep(500)
  t = await page.text()
  check('notes and proposal are drafted inside the app in under 3 minutes', draftSeconds < 180, `${draftSeconds} s`)
  const titles = await page.eval("[...document.querySelectorAll('.proposal h3')].map(h => h.textContent.trim())")
  check('the proposal has its sections, pricing after the scope', titles.indexOf('Inversión') > titles.indexOf('Alcance') && titles.includes('Resumen'), titles.join(' > '))
  check('prices and terms come from the profile', t.includes('650 MXN por hora') && t.includes('Sitio web de hasta 5 secciones: 24,000 MXN') && t.includes('50% de anticipo y 50% a la entrega.'))
  const summary = await page.eval("document.querySelector('[data-section=summary] p').textContent")
  check('the summary has no price', !/\$|MXN|\d{4,}/.test(summary), summary.slice(0, 80))
  check('scope items have source links', (await page.eval("document.querySelectorAll('[data-section=scope] .chip').length")) > 0)
  await page.eval("document.querySelector('[data-section=scope] .chip').click()")
  await page.waitFor("document.querySelector('[data-section=scope] .quote')", 3000, 'quote')
  const quote = await page.eval("document.querySelector('[data-section=scope] .quote').innerText")
  check('clicking a source shows the quote and its time', /\d+:\d{2}/.test(quote) && quote.includes('“'), quote)
  await page.viewportShot(path.join(out, '07-draft.png'))

  // ---- 6. Edit and export
  await page.click('Edit proposal', 'button')
  await page.waitFor("document.querySelector('.editor')", 5000, 'editor')
  await page.fill('[data-section=summary] textarea', 'Resumen revisado por la freelancer.')
  await page.click('Save changes', 'button')
  await page.waitFor("document.body.innerText.includes('Changes saved.')", 8000, 'saved')
  check('an edit is saved', true)
  const md = await page.eval(`fetch(${JSON.stringify(`${apiBase}/calls/${callId}/draft/export?format=md`)}).then(r => r.text())`)
  check('the Markdown export has the edit, the rates and the terms', md.includes('Resumen revisado por la freelancer.') && md.includes('650 MXN por hora') && md.includes('50% de anticipo'), md.split('\n')[0])
  const pdfHead = await page.eval(`fetch(${JSON.stringify(`${apiBase}/calls/${callId}/draft/export?format=pdf`)}).then(async r => { const b = new Uint8Array(await r.arrayBuffer()); return [r.headers.get('content-type'), String.fromCharCode(...b.slice(0, 5)), b.length] })`)
  check('the PDF export is a PDF', pdfHead[0] === 'application/pdf' && pdfHead[1] === '%PDF-', `${pdfHead[2]} bytes`)
  await page.click('Download Markdown', 'button')
  await sleep(2500)
  const saved = existsSync(downloads) ? readdirSync(downloads) : []
  log(`download button clicked; files in the download folder: ${saved.join(', ') || 'none (Electron shows its own Save dialog)'}`)
  await page.viewportShot(path.join(out, '08-edited.png'))

  // ---- 7. Privacy: after setup, the app holds only loopback connections
  const mine = tree(shell.pid).map(p => p.pid)
  const all = connections(mine)
  const loopback = a => a.startsWith('127.0.0.1:') || a.startsWith('[::1]:') || a.startsWith('*:')
  const external = all.filter(c => c.includes('->') && !loopback(c.split('->')[1]))
  check('the app holds no connection to anything but this computer', external.length === 0, external.join(' | ') || `${all.length} local sockets`)
  check('the app and the engines use their own data folder', existsSync(path.join(userData, 'data')) && existsSync(path.join(userData, 'models', 'whisper')) && existsSync(path.join(userData, 'models', 'ollama', 'blobs')))
  check('the whisper model file is the verified one', statSync(path.join(userData, 'models', 'whisper', 'ggml-large-v3-turbo-q5_0.bin')).size === 574041195)

  // ---- 8. Quit
  const before = tree(shell.pid).map(p => p.pid)
  shell.kill('SIGTERM')
  await new Promise(r => shell.once('exit', r))
  await sleep(2000)
  check('quitting stops the shell, Ollama (with the loaded model), the api and every helper', before.every(pid => !alive(pid)), `${before.length} processes`)
} catch (error) {
  results.push(['FAIL', 'script error', String(error.stack ?? error)])
  log(`script error: ${error.message}`)
} finally {
  console.log('\n' + results.map(r => r.join(' | ')).join('\n'))
  console.log('console problems:', JSON.stringify((page?.logs ?? []).slice(0, 8)))
  console.log('user data folder:', userData)
  try { for (const p of tree(shell.pid)) process.kill(p.pid, 'SIGKILL') } catch { /* gone */ }
}
