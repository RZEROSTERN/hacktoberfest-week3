// Starts the desktop shell for real (bundled Ollama + packaged api + generated web app) in a throwaway
// user-data folder and checks it from the outside over the DevTools protocol and with ps/lsof.
//   node scripts/shell-check.mjs                       the shell from this repository (npm run build first)
//   APP_BIN=/path/Scopewise.app/Contents/MacOS/Scopewise node scripts/shell-check.mjs   the packaged app
// Needs: `make desktop-resources` (or the individual build scripts) and `npm run build` in desktop/.
import { execFileSync, spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Page } from '../../web/ui-check/cdp.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const desktop = path.resolve(here, '..')
const out = process.env.UI_OUT ?? path.join(desktop, '..', '.dev', 'shell-check')
mkdirSync(out, { recursive: true })
const userData = mkdtempSync(path.join(process.env.SCRATCH ?? tmpdir(), 'scopewise-shell-'))
const CDP_PORT = 9340
const appBin = process.env.APP_BIN
const sleep = ms => new Promise(r => setTimeout(r, ms))
const results = []
const check = (name, ok, detail = '') => results.push([ok ? 'PASS' : 'FAIL', name, detail])

function processes() {
  const text = execFileSync('ps', ['-axo', 'pid=,ppid=,pgid=,command='], { encoding: 'utf8' })
  return text.split('\n').map((l) => {
    const m = l.trim().match(/^(\d+)\s+(\d+)\s+(\d+)\s+(.*)$/)
    return m ? { pid: +m[1], ppid: +m[2], pgid: +m[3], command: m[4] } : null
  }).filter(Boolean)
}
function tree(rootPid) {
  const all = processes()
  const seen = new Set([rootPid])
  let grew = true
  while (grew) {
    grew = false
    for (const p of all) if (seen.has(p.ppid) && !seen.has(p.pid)) { seen.add(p.pid); grew = true }
  }
  return all.filter(p => seen.has(p.pid))
}
function listenPorts(pids) {
  try {
    const text = execFileSync('lsof', ['-nP', '-iTCP', '-sTCP:LISTEN', '-a', '-p', pids.join(','), '-Fn'], { encoding: 'utf8' })
    return text.split('\n').filter(l => l.startsWith('n')).map(l => ({ address: l.slice(1, l.lastIndexOf(':')), port: +l.slice(l.lastIndexOf(':') + 1) }))
  } catch { return [] }
}
const alive = (pid) => { try { process.kill(pid, 0); return true } catch { return false } }

// The real Electron binary, not node_modules/.bin/electron: that is a Node wrapper, and killing the
// wrapper would not kill the app.
const electronBinary = path.join(desktop, 'node_modules', 'electron', 'dist', readFileSync(path.join(desktop, 'node_modules', 'electron', 'path.txt'), 'utf8').trim())
const command = appBin ?? electronBinary
const args = [...(appBin ? [] : ['.']), `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${userData}`]
function startShell() {
  // VS Code-based terminals set ELECTRON_RUN_AS_NODE, which would make Electron behave as plain Node.
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => key !== 'ELECTRON_RUN_AS_NODE'))
  const child = spawn(command, args, { cwd: desktop, stdio: ['ignore', 'ignore', 'pipe'], env: { ...env, ELECTRON_ENABLE_LOGGING: '1' } })
  child.stderr.resume() // the shell's own log output is not needed here, but must not fill the pipe
  return child
}

async function connect() {
  for (let i = 0; i < 120; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json()
      const page = list.find(t => t.type === 'page')
      if (page) return await Page.connect(page.webSocketDebuggerUrl)
    } catch { /* not up yet */ }
    await sleep(250)
  }
  throw new Error('the shell window did not appear')
}

let shell = startShell()
let page
try {
  page = await connect()
  const pidFile = path.join(userData, 'services.json')

  // 1. The start page appears at once, then the app replaces it when both services answer.
  await page.waitFor("location.protocol === 'app:' && document.querySelector('main h1')", 120000, 'the app to load')
  check('the app loads from its own app:// address after both services are healthy', true, await page.eval('location.href'))
  await sleep(500)

  // 2. Both services run, loopback only, started in order (Ollama is the older process).
  const kids = tree(shell.pid).filter(p => /\/ollama serve|ollama\/ollama|scopewise-api|llama-server/.test(p.command))
  const ollama = kids.find(p => /ollama\/ollama serve|ollama serve/.test(p.command))
  const api = kids.find(p => p.command.includes('scopewise-api'))
  check('the bundled Ollama and the packaged api are both running', !!ollama && !!api, kids.map(k => path.basename(k.command.split(' ')[0])).join(', '))
  const opened = listenPorts(tree(shell.pid).map(p => p.pid)).filter(l => l.port !== CDP_PORT)
  check('every port the app opens is loopback-only', opened.length >= 2 && opened.every(l => l.address === '127.0.0.1'), opened.map(l => `${l.address}:${l.port}`).join(' '))
  check('the pid file lists both services', existsSync(pidFile) && Object.keys(JSON.parse(readFileSync(pidFile, 'utf8'))).sort().join() === 'api,ollama')

  // 3. The window is sandboxed and knows only where the api is.
  const bridge = await page.eval('JSON.stringify(window.desktop)')
  check('the page gets the api address from the preload', /^\{"apiBase":"http:\/\/127\.0\.0\.1:\d+"\}$/.test(bridge), bridge)
  const apiBase = JSON.parse(bridge).apiBase
  check('no Node access in the page', await page.eval("typeof require === 'undefined' && typeof process === 'undefined' && typeof module === 'undefined'"))
  // Note: Runtime.evaluate is exempt from the page's policy, so eval() here would prove nothing. Read the
  // header the page was served with, and watch the browser itself reject an injected script.
  const policy = await page.eval("fetch(location.href).then(r => r.headers.get('content-security-policy'))")
  check('pages are served with a strict content security policy', /default-src 'none'/.test(policy) && !/unsafe-eval/.test(policy) && !/script-src[^;]*unsafe-inline/.test(policy), policy)
  check('an injected inline script is rejected by the browser', await page.eval(`(async () => {
    const violations = []
    document.addEventListener('securitypolicyviolation', e => violations.push(e.violatedDirective))
    const s = document.createElement('script'); s.textContent = 'window.__injected = true'; document.head.appendChild(s)
    await new Promise(r => setTimeout(r, 300)); return window.__injected !== true && violations.some(v => v.startsWith('script-src')) })()`))
  check('the page cannot reach the internet', await page.eval("fetch('https://example.com/', { mode: 'no-cors' }).then(() => false, () => true)"))
  const ollamaPort = listenPorts([ollama.pid])[0]?.port
  check('the page cannot talk to Ollama directly (only the api can)', !!ollamaPort && await page.eval(`fetch('http://127.0.0.1:${ollamaPort}/api/tags').then(() => false, () => true)`), `ollama on ${ollamaPort}`)
  check('the api answers the page with its CORS origin', await page.eval(`fetch(${JSON.stringify(apiBase + '/health')}).then(r => r.ok, () => false)`))

  // 4. A fresh install has no models, and that is true because the app uses ITS Ollama, not the system one.
  const status = await page.eval(`fetch(${JSON.stringify(apiBase + '/setup/status')}).then(r => r.json())`)
  check('a new data folder asks for the models even if the system Ollama has some', status.ready === false, JSON.stringify({ ready: status.ready, problem: status.problem }))
  check('the first screen is the model request', (await page.text()).includes('Download'), (await page.text()).slice(0, 80))
  await page.shot(path.join(out, 'shell-setup.png'))

  // 5. Third-party notices.
  await page.goto('app://scopewise/notices', "location.pathname === '/notices' && document.querySelector('main h1')")
  const notices = await page.text()
  check('the notices screen lists the engines and their licenses', ['Ollama', 'whisper.cpp', 'Gemma 4', 'Apache License 2.0', 'Electron'].every(w => notices.includes(w)))
  await page.shot(path.join(out, 'shell-notices.png'))
  await page.goto('app://scopewise/calls/does-not-exist', "location.pathname.startsWith('/calls') || location.pathname === '/setup'")
  check('a deep link that is not a pre-rendered page still loads the app', (await page.text()).length > 0)

  // 6. A crashed service is restarted once and the page keeps working.
  const apiPid = api.pid
  process.kill(apiPid, 'SIGKILL')
  await sleep(500)
  await page.waitFor(`fetch(${JSON.stringify(apiBase + '/health')}).then(r => r.ok, () => false)`, 60000, 'the api to come back')
  const newApi = tree(shell.pid).find(p => p.command.includes('scopewise-api') && p.pid !== apiPid)
  check('a crashed api is restarted on the same address', !!newApi && !alive(apiPid), `old ${apiPid}, new ${newApi?.pid}`)

  // 7. Quitting stops everything.
  const before = tree(shell.pid).map(p => p.pid)
  shell.kill('SIGTERM')
  await new Promise(r => shell.once('exit', r))
  await sleep(1500)
  const left = before.filter(alive)
  check('quitting the app stops the shell, Ollama, the api and every helper', left.length === 0, left.length ? `still running: ${left}` : `${before.length} processes ended`)
  check('the pid file is removed on a clean quit', !existsSync(pidFile))

  // 8. A hard kill of the shell: the api follows by itself, and the next start cleans up what is left.
  shell = startShell()
  page = await connect()
  await page.waitFor("location.protocol === 'app:' && document.querySelector('main h1')", 120000, 'the app to load again')
  const group = tree(shell.pid).filter(p => /ollama serve|ollama\/ollama|scopewise-api/.test(p.command))
  const oldOllama = group.find(p => /ollama/.test(p.command) && !p.command.includes('api'))
  const oldApi = group.find(p => p.command.includes('scopewise-api'))
  shell.kill('SIGKILL')
  const apiGone = await (async () => { for (let i = 0; i < 40; i++) { if (!alive(oldApi.pid)) return true; await sleep(250) } return false })()
  check('after a force quit the api stops by itself within seconds', apiGone, `api pid ${oldApi.pid}`)
  check('after a force quit Ollama is still there until the next start', alive(oldOllama.pid), `ollama pid ${oldOllama.pid}`)
  shell = startShell()
  page = await connect()
  await page.waitFor("location.protocol === 'app:' && document.querySelector('main h1')", 120000, 'the app to load a third time')
  check('the next start removes the Ollama that was left behind', !alive(oldOllama.pid))
} catch (error) {
  results.push(['FAIL', 'script error', String(error.stack ?? error)])
} finally {
  console.log(results.map(r => r.join(' | ')).join('\n'))
  console.log('console problems:', JSON.stringify((page?.logs ?? []).slice(0, 8)))
  try { for (const p of tree(shell.pid)) process.kill(p.pid, 'SIGKILL') } catch { /* already gone */ }
  try { shell.kill('SIGKILL') } catch { /* already gone */ }
}
