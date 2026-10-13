// The first-launch wizard and Settings against the real engines, from a fresh install state.
// Needs: Ollama running with the recommended model installed, `npm run dev` on localhost:3000, and
// ROOT (the repository folder). The script starts and stops the api itself so it can simulate the app
// being quit in the middle of a download. It downloads the real speech model (about 574 MB) and pulls
// a tiny model (about 270 MB). The tiny model is removed again at the end.
import { spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { createReadStream, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { launch, sleep } from './cdp.mjs'

const ROOT = process.env.ROOT
const S = process.env.UI_OUT ?? new URL('../../.dev/ui-check', import.meta.url).pathname
const WEB = process.env.WEB_URL ?? 'http://localhost:3000'
const API = 'http://127.0.0.1:8765'
const OLLAMA = process.env.SCOPEWISE_OLLAMA_URL ?? 'http://127.0.0.1:11434'
const GOOD = 'gemma4:e4b'
const TINY = 'smollm2:135m'
const DATA = `${ROOT}/.dev/setup-check`
mkdirSync(S, { recursive: true })

const results = []
const check = (name, ok, detail = '') => results.push([ok ? 'PASS' : 'FAIL', name, String(detail).slice(0, 160)])

let apiProcess = null
function startApi() {
  apiProcess = spawn('make', ['dev-api'], {
    cwd: ROOT,
    detached: true, // its own process group, so the whole tree can be killed like a quit
    stdio: 'ignore',
    env: { ...process.env, SCOPEWISE_DATA_DIR: `${DATA}/data`, SCOPEWISE_MODELS_DIR: `${DATA}/models`, SCOPEWISE_LLM_MODEL: '' },
  })
}
function killApi(signal = 'SIGTERM') {
  if (apiProcess) {
    try { process.kill(-apiProcess.pid, signal) } catch { /* already gone */ }
    apiProcess = null
  }
}
async function waitApi(up = true, timeout = 60000) {
  const end = Date.now() + timeout
  while (Date.now() < end) {
    let ok = false
    try { ok = (await fetch(`${API}/health`)).ok } catch { /* down */ }
    if (ok === up) return
    await sleep(300)
  }
  throw new Error(`api did not ${up ? 'start' : 'stop'}`)
}
const apiJson = async path => (await fetch(`${API}${path}`)).json()
const ollamaTags = async () => (await (await fetch(`${OLLAMA}/api/tags`)).json()).models.map(m => m.name)
const sha256 = file => new Promise((resolve, reject) => {
  const h = createHash('sha256')
  createReadStream(file).on('data', c => h.update(c)).on('end', () => resolve(h.digest('hex'))).on('error', reject)
})

rmSync(DATA, { recursive: true, force: true })
const { proc, page } = await launch(9338, S)
const text = () => page.text()
const has = async s => (await text()).includes(s)

try {
  if (!(await ollamaTags()).includes(GOOD)) throw new Error(`${GOOD} must be installed in Ollama for this check`)
  await fetch(`${OLLAMA}/api/delete`, { method: 'DELETE', body: JSON.stringify({ model: TINY }) }) // start without the tiny model
  startApi()
  await waitApi()
  await page.resize(900)

  // --- 1. first launch: everything is sent to the request screen
  await page.goto(`${WEB}/`, "document.querySelector('main h1')")
  await page.waitFor("document.body.innerText.includes('Welcome to Scopewise')", 20000, 'request screen')
  check('a first launch lands on the model request, not on the app', page && (await page.eval('location.pathname')) === '/setup')
  let t = await text()
  check('it explains the offline, private download', /fully offline/.test(t) && /downloaded once to this computer/.test(t))
  check('the recommended model is preselected and marked', await page.eval(`document.querySelector('input[type=radio][value="${GOOD}"]').checked`) && t.includes('Recommended'))
  check('it shows size, memory, license and a note for the model', /6\.6 GB download/.test(t) && /8 GB of memory/.test(t) && /Apache 2\.0/.test(t) && /12 of 13 key facts/.test(t))
  const all = await page.eval('document.body.textContent') // includes the collapsed sections
  check('other tested models are listed, and one is not recommended for this computer', all.includes('Qwen 3.5 9B') && all.includes('Not recommended for this computer'), (await page.eval("[...document.querySelectorAll('.badge.warn')].map(b => b.closest('.choice').querySelector('strong').textContent).join(', ')")))
  check('Advanced offers any Ollama model with a library link and a quality warning', all.includes('Advanced: use another model from Ollama') && all.includes('may give lower quality') && (await page.eval("!!document.querySelector('a[href=\"https://ollama.com/library\"]')")))
  check('it names the speech model and its size', /Whisper large-v3-turbo/.test(t) && /574 MB/.test(t))
  check('it shows the total download, the disk needed and the disk available', /Total download:/.test(t) && /Free disk space needed:/.test(t) && /Available:/.test(t))
  check('it recommends Wi-Fi', /Wi-Fi/.test(t))
  check('it offers "Download now" and "Not now"', ['Download now', 'Not now'].every(b => t.includes(b)))
  await page.shot(`${S}/30-request.png`)

  // --- 2. "Not now": nothing else works, and the same request comes back
  await page.click('Not now', 'button')
  await page.waitFor("document.body.innerText.includes('Scopewise needs its models')", 5000, 'later screen')
  await page.goto(`${WEB}/profile`, "document.querySelector('main h1')")
  check('with "Not now", other pages still lead back to the setup', (await page.eval('location.pathname')) === '/setup')
  await page.goto(`${WEB}/`, "document.querySelector('main h1')")
  check('on the next launch the same request is shown again', await has('Welcome to Scopewise'))

  // --- 3. names are checked
  const typeModel = async name => {
    await page.eval("document.querySelector('input[type=radio][value=__custom__]').click()")
    await page.fill('input[aria-label="Ollama model name and tag"]', name)
  }
  await typeModel('gemma4:cloud')
  await page.click('Download now', 'button')
  await page.waitFor("document.body.innerText.includes('send your calls to a server')", 6000, 'cloud refusal')
  check('a cloud model is refused with a plain explanation', true)
  await typeModel('bad name!')
  await page.click('Download now', 'button')
  await page.waitFor("document.body.innerText.includes('not a valid model name')", 6000, 'invalid name')
  check('a malformed name is refused', true)
  await typeModel('no-such-model:1b')
  await page.click('Download now', 'button')
  await page.waitFor("document.body.innerText.includes('No model with that name exists')", 20000, 'unknown model failure')
  check('a model that does not exist fails with a clear message and Try again', (await has('Try again')) && (await has('Choose another model')))
  await page.shot(`${S}/31-failed.png`)
  await page.click('Choose another model', 'button')
  await page.waitFor("document.body.innerText.includes('Welcome to Scopewise')", 5000, 'back to the list')
  check('"Choose another model" goes back to the list', true)

  // --- 4. a real download of the tiny model and the real speech model, with progress, pause and resume
  await typeModel(TINY)
  await page.click('Download now', 'button')
  await page.waitFor("document.querySelector('[data-step=engine]')", 10000, 'progress screen')
  t = await text()
  check('the progress screen lists the six steps in order', JSON.stringify(await page.eval("[...document.querySelectorAll('.steps li')].map(li => li.dataset.step)")) === JSON.stringify(['engine', 'llm', 'whisper', 'verify', 'compat', 'ready']))
  check('it has an overall progress bar and a prominent language-model step', !!(await page.eval("document.querySelector('.setup-progress > .progress progress')")) && !!(await page.eval("document.querySelector('.steps li.main[data-step=llm]')")))
  await page.waitFor("document.querySelector('[data-step=whisper].running .progress')", 60000, 'speech model downloading')
  await sleep(1500)
  const line = await page.eval("document.querySelector('[data-step=whisper] .progress span').textContent")
  check('a download shows percentage, "x MB of y MB", speed and time left', /\d+%/.test(line) && /\d+ MB of 574 MB/.test(line) && /MB\/s/.test(line) && /left/.test(line), line)
  await page.shot(`${S}/32-progress.png`)

  await page.click('Pause', 'button')
  await page.waitFor("document.body.innerText.includes('Paused. Nothing is downloading.')", 15000, 'paused')
  check('a download can be paused', (await has('Resume')) && !(await has('Pausing…')))
  const pausedAt = (await apiJson('/setup/progress')).steps[2].completed
  await page.shot(`${S}/33-paused.png`)
  await page.click('Resume', 'button')
  await page.waitFor("document.body.innerText.includes('Everything is ready') || !!document.querySelector('.setup-progress .error')", 180000, 'run end')
  const end = await apiJson('/setup/progress')
  check('resuming continued the speech model from where it stopped', end.steps[2].state === 'done' && end.steps[2].completed >= pausedAt, `paused at ${pausedAt}`)

  // --- 5. the model that cannot do the task is refused, with a way out
  check('the tiny model fails the compatibility check with a plain explanation', end.state === 'compat_failed' && /too small|structured notes|writing tasks/.test(end.error_message ?? ''), end.error_message)
  t = await text()
  check('it offers the recommended model and a way to choose another', t.includes('Use the recommended model (Gemma 4 E4B)') && t.includes('Choose another model'))
  await page.shot(`${S}/34-compat-failed.png`)
  check('the app is still not usable (no model selected)', (await apiJson('/setup/status')).ready === false)
  await page.click('Use the recommended model', 'button')
  await page.waitFor("document.body.innerText.includes('Everything is ready')", 240000, 'recommended model ready')
  const done = await apiJson('/setup/progress')
  check('the recommended model passes the real check; downloads already done are skipped', done.state === 'done' && done.steps.find(s => s.id === 'llm').skipped && done.steps.find(s => s.id === 'whisper').skipped)
  await page.shot(`${S}/35-ready.png`)
  await page.click('Start using Scopewise', 'button')
  await page.waitFor("document.querySelector('main h1') && document.querySelector('main h1').textContent.includes('Your calls')", 10000, 'home')
  check('"Start using Scopewise" opens the app, and it stays open afterwards', true)
  await page.goto(`${WEB}/profile`, "document.querySelector('main h1')")
  check('after setup the request never appears again', (await page.eval('location.pathname')) === '/profile')

  // --- 6. Settings
  await page.goto(`${WEB}/settings`, "document.querySelector('main h1')")
  await page.waitFor("document.querySelector('.models li')", 10000, 'models list')
  t = await text()
  const rows = await page.eval("[...document.querySelectorAll('.models li')].map(li => li.dataset.model + ' | ' + li.innerText.replace(/\\n/g, ' '))")
  check('Settings lists the models, which is in use, and which is unchecked', rows.some(r => r.startsWith(GOOD) && r.includes('In use')) && rows.some(r => r.startsWith(TINY) && r.includes('Not checked yet')), rows.join(' // '))
  check('Settings shows the speech model and this computer', t.includes('On this computer') && /of free disk space/.test(t))
  await page.shot(`${S}/36-settings.png`)
  await page.eval(`[...document.querySelectorAll('.models li')].find(li => li.dataset.model === '${TINY}').querySelectorAll('button')[1].click()`) // Delete
  await page.waitFor(`![...document.querySelectorAll('.models li')].some(li => li.dataset.model === '${TINY}')`, 15000, 'tiny model removed from the list')
  check('a model can be deleted to free disk space', !(await ollamaTags()).includes(TINY))

  // --- 7. quit in the middle of a download, then come back
  await page.eval("[...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Delete' && b.closest('.card')).click()")
  await page.waitFor("document.body.innerText.includes('Welcome to Scopewise')", 15000, 'back to setup after deleting the speech model')
  check('deleting the speech model sends the app back to the setup request', (await has('Not downloaded')) || /574 MB/.test(await text()))
  await page.click('Download now', 'button')
  const dl = async () => (await apiJson('/setup/progress')).steps[2].completed
  const until = Date.now() + 60000
  while (Date.now() < until && (await dl()) < 200_000_000) await sleep(150)
  const before = await dl()
  killApi('SIGKILL') // the app is quit without any chance to clean up
  await waitApi(false, 15000)
  startApi()
  await waitApi()
  await page.goto(`${WEB}/`, "document.querySelector('main h1')")
  await page.waitFor("document.body.innerText.includes('interrupted when Scopewise closed')", 20000, 'interrupted prompt')
  check('after quitting mid-download the user is asked whether to continue (nothing restarts silently)', (await has('Resume')) && (await apiJson('/setup/progress')).state === 'interrupted', `killed at ${before}`)
  check('the progress it had reached is remembered', (await apiJson('/setup/progress')).steps[2].completed >= before * 0.9)
  await page.shot(`${S}/37-interrupted.png`)
  await page.click('Resume', 'button')
  await page.waitFor("document.body.innerText.includes('Everything is ready')", 240000, 'finished after resume')
  const catalog = JSON.parse(readFileSync(`${ROOT}/api/data/models.json`, 'utf8'))
  const file = `${DATA}/models/whisper/${catalog.whisper.file}`
  check('the speech model was completed and matches its checksum', (await sha256(file)) === catalog.whisper.sha256)

  // --- 8. phone width
  await page.click('Start using Scopewise', 'button')
  await page.resize(390, 800)
  await page.goto(`${WEB}/settings`, "document.querySelector('main h1')")
  await page.waitFor("document.querySelector('.models li')", 10000)
  check('Settings has no horizontal scroll on a phone-width screen', !(await page.eval('document.documentElement.scrollWidth > document.documentElement.clientWidth')))
  await page.shot(`${S}/38-settings-mobile.png`)

  // --- 9. the engine is not answering
  killApi('SIGTERM')
  await waitApi(false, 15000)
  await page.resize(900)
  await page.goto(`${WEB}/setup`, "document.querySelector('main h1')")
  await page.waitFor("document.body.innerText.includes('Could not reach the local engine')", 15000, 'engine error')
  check('with the engine down the page explains it instead of asking for downloads', !(await has('Download now')))
  await page.shot(`${S}/39-engine-down.png`)
} catch (e) {
  results.push(['FAIL', 'script error', String(e.message)])
} finally {
  console.log(results.map(r => r.join(' | ')).join('\n'))
  console.log('browser console problems:', JSON.stringify(page.logs.slice(0, 8)))
  console.log('dialogs seen:', JSON.stringify(page.dialogs))
  killApi('SIGKILL')
  try { await fetch(`${OLLAMA}/api/delete`, { method: 'DELETE', body: JSON.stringify({ model: TINY }) }) } catch { /* ignore */ }
  proc.kill()
}
