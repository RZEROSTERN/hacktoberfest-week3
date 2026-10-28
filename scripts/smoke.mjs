// Starts the programs an installer carries and checks they work, from the folder they were packaged into:
//   node scripts/smoke.mjs --resources <the packaged app's resources folder>
//   node scripts/smoke.mjs                         (checks desktop/build, what is about to be packaged)
// 1. every program is there and starts (Ollama --version, whisper-cli --help, FFmpeg -version and its license);
// 2. the packaged api starts on a test port and answers /health;
// 3. through that api, a short call is uploaded, converted and transcribed with a small model, in a folder whose
//    name has an accent (as a Windows user name may), which proves the converter, whisper-cli and the paths.
// The job fails if any of it fails.
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { buildDir, capture, download, downloadsDir, platformId, programPaths, root, versions } from './lib.mjs'

const id = platformId()
const argIndex = process.argv.indexOf('--resources')
const resources = path.resolve(argIndex > 0 ? process.argv[argIndex + 1] : buildDir)
const programs = programPaths(id)
const at = parts => path.join(resources, ...parts)
const results = []
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'} | ${name}${detail ? ` | ${String(detail).slice(0, 300)}` : ''}`)
}
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

function killTree(child) {
  if (!child.pid) return
  if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  else {
    try {
      process.kill(-child.pid, 'SIGKILL')
    } catch {
      /* already gone */
    }
  }
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address()
      server.close(() => resolve(port))
    })
  })
}

async function until(fn, timeoutMs, stepMs = 500) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const value = await fn()
    if (value) return value
    if (Date.now() > deadline) return null
    await sleep(stepMs)
  }
}

console.log(`Smoke test of ${resources} on ${id}`)

// 1. The programs.
const required = { ollama: programs.ollama, api: programs.api, whisper: programs.whisper, ...(programs.ffmpeg ? { ffmpeg: programs.ffmpeg } : {}) }
for (const [name, parts] of Object.entries(required)) check(`${name} is packaged`, fs.existsSync(at(parts)), path.relative(resources, at(parts)))
if (results.some(r => !r.ok)) finish()

const ollamaVersion = capture(at(programs.ollama), ['--version'], { timeout: 60_000 })
const ollamaWanted = versions.ollama.version.replace(/^v/, '')
check('the bundled Ollama reports its version', ollamaVersion.status === 0 && `${ollamaVersion.stdout}${ollamaVersion.stderr}`.includes(ollamaWanted), `${ollamaVersion.stdout}${ollamaVersion.stderr}`.trim().split('\n')[0])

const whisperHelp = capture(at(programs.whisper), ['--help'], { timeout: 60_000 })
check('whisper-cli starts', whisperHelp.status === 0 && /usage/i.test(`${whisperHelp.stdout}${whisperHelp.stderr}`), `exit ${whisperHelp.status}`)

if (programs.ffmpeg) {
  const ffmpeg = capture(at(programs.ffmpeg), ['-hide_banner', '-version'], { timeout: 60_000 })
  const info = `${ffmpeg.stdout}${ffmpeg.stderr}`
  check('FFmpeg starts', ffmpeg.status === 0 && info.includes(`ffmpeg version ${versions.ffmpeg.version}`), info.split('\n')[0])
  check('FFmpeg is an LGPL-only build', !/--enable-(gpl|nonfree|version3)/.test(info))
}

// 2 and 3. The packaged api, started the way the desktop shell starts it.
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'postcall smoke Ramírez '))
const port = await freePort()
const model = await download(versions.smokeModel.url, path.join(downloadsDir, versions.smokeModel.file), versions.smokeModel.sha256)
const env = {
  ...process.env,
  POSTCALL_HOST: '127.0.0.1',
  POSTCALL_PORT: String(port),
  POSTCALL_DATA_DIR: path.join(work, 'data'),
  POSTCALL_MODELS_DIR: path.join(work, 'models'),
  POSTCALL_OLLAMA_URL: 'http://127.0.0.1:1', // no language model is needed here
  POSTCALL_WHISPER_CLI: at(programs.whisper),
  POSTCALL_WHISPER_MODEL: model,
  ...(programs.ffmpeg ? { POSTCALL_FFMPEG: at(programs.ffmpeg) } : {}),
}
const logFile = path.join(work, 'api.log')
const log = fs.openSync(logFile, 'w')
const api = spawn(at(programs.api), [], { env, stdio: ['ignore', log, log], detached: process.platform !== 'win32', windowsHide: true })
let exited = null
api.once('exit', code => {
  exited = code
})
const base = `http://127.0.0.1:${port}`

try {
  const healthy = await until(async () => {
    if (exited !== null) return 'exited'
    try {
      return (await fetch(`${base}/health`, { signal: AbortSignal.timeout(2000) })).ok
    } catch {
      return false
    }
  }, 180_000)
  check('the packaged api answers /health on a test port', healthy === true, healthy === 'exited' ? `it exited with ${exited}` : `port ${port}`)

  if (healthy === true) {
    const form = new FormData()
    const clip = path.join(root, 'api', 'tests', 'data', 'clip.mp3')
    form.append('file', new Blob([fs.readFileSync(clip)]), 'clip.mp3')
    const upload = await fetch(`${base}/calls`, { method: 'POST', body: form })
    check('a call can be uploaded', upload.status === 202, `HTTP ${upload.status}`)
    if (upload.status === 202) {
      const { id: callId } = await upload.json()
      const call = await until(async () => {
        const body = await (await fetch(`${base}/calls/${callId}`)).json()
        return ['done', 'failed'].includes(body.status) ? body : null
      }, 240_000, 1000)
      check('the call is converted and transcribed (accented folder, small model)', call?.status === 'done', call ? `${call.status} ${call.error_code ?? ''}` : 'timed out')
      if (call?.status === 'done') {
        const transcript = await (await fetch(`${base}/calls/${callId}/transcript`)).json()
        const words = (transcript.segments ?? []).map(s => s.text).join(' ').trim()
        check('the transcript has text', words.length > 10, words)
      }
    }
  }
} catch (error) {
  check('the api smoke test ran', false, error.stack ?? error)
} finally {
  killTree(api)
  fs.closeSync(log)
  if (results.some(r => !r.ok)) console.log(`--- api log (${logFile}):\n${fs.readFileSync(logFile, 'utf8').slice(-1500)}`)
  await sleep(500)
  fs.rmSync(work, { recursive: true, force: true })
}
finish()

function finish() {
  const failed = results.filter(r => !r.ok)
  const lines = [`### Smoke test, ${id}`, '', ...results.map(r => `- ${r.ok ? 'PASS' : '**FAIL**'}: ${r.name}`), '']
  if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${lines.join('\n')}\n`)
  console.log(failed.length === 0 ? `\nAll ${results.length} checks passed.` : `\n${failed.length} of ${results.length} checks failed.`)
  process.exit(failed.length === 0 ? 0 : 1)
}
