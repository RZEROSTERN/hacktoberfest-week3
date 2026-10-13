// Minimal Chrome DevTools Protocol driver for looking at the real UI: drives the installed Google Chrome
// headlessly, with no dependencies (Node 24 has fetch and WebSocket).
import { spawn } from 'node:child_process'
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const sleep = ms => new Promise(r => setTimeout(r, ms))

export async function launch(port = 9333, scratch) {
  mkdirSync(scratch, { recursive: true })
  const dir = mkdtempSync(`${scratch}/chrome-`)
  const proc = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${dir}`,
    '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--hide-scrollbars', 'about:blank',
  ], { stdio: 'ignore' })
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()
      const page = list.find(t => t.type === 'page')
      if (page) return { proc, page: await Page.connect(page.webSocketDebuggerUrl) }
    } catch { /* browser not ready yet */ }
    await sleep(250)
  }
  proc.kill()
  throw new Error('Chrome did not start')
}

export class Page {
  static async connect(url) {
    const ws = new WebSocket(url)
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
    const page = new Page(ws)
    await page.send('Page.enable')
    await page.send('Runtime.enable')
    return page
  }

  constructor(ws) {
    this.ws = ws
    this.id = 0
    this.pending = new Map()
    this.logs = []
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.id && this.pending.has(msg.id)) {
        const { res, rej } = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result)
      } else if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(msg.params.type)) {
        this.logs.push(`${msg.params.type}: ${msg.params.args.map(a => a.value ?? a.description).join(' ')}`)
      } else if (msg.method === 'Runtime.exceptionThrown') {
        this.logs.push(`exception: ${msg.params.exceptionDetails.exception?.description ?? msg.params.exceptionDetails.text}`)
      }
    }
  }

  send(method, params = {}) {
    const id = ++this.id
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((res, rej) => this.pending.set(id, { res, rej }))
  }

  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text)
    return r.result.value
  }

  async waitFor(expression, timeout = 15000, what = expression) {
    const end = Date.now() + timeout
    while (Date.now() < end) {
      try { if (await this.eval(expression)) return } catch { /* page still loading */ }
      await sleep(150)
    }
    throw new Error(`timed out waiting for: ${what}`)
  }

  async goto(url, readyExpr = "document.querySelector('main h1')") {
    await this.send('Page.navigate', { url })
    await this.waitFor(readyExpr, 20000, `page ${url}`)
    await sleep(300)
  }

  async resize(width, height = 900) {
    await this.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 })
  }

  async shot(path, maxHeight = 5000) {
    const m = await this.send('Page.getLayoutMetrics')
    const h = Math.min(Math.ceil(m.cssContentSize.height), maxHeight)
    const w = Math.ceil(m.cssContentSize.width)
    const r = await this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: w, height: h, scale: 1 } })
    writeFileSync(path, Buffer.from(r.data, 'base64'))
  }

  // Vue's v-model listens to `input`, so set the value natively and dispatch the event.
  fill(selector, value) {
    return this.eval(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)})
      const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)})
      el.dispatchEvent(new Event('input', { bubbles: true }))
      return true })()`)
  }

  // Click the first button/link whose visible text includes `text`.
  click(text, selector = 'button, a') {
    return this.eval(`(() => {
      const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find(e => e.textContent.trim().includes(${JSON.stringify(text)}))
      if (!el) return false
      el.click(); return true })()`)
  }

  text() { return this.eval('document.body.innerText') }
}

export { sleep }
