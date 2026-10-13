// Editing and export on a finished draft: edit, remove, add, save, rules, unsaved-changes guard, downloads.
// Needs the dev api + web, CALL_ID of a call with a finished draft, and a saved profile.
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { launch, sleep } from './cdp.mjs'

const S = process.env.UI_OUT ?? new URL('../../.dev/ui-check', import.meta.url).pathname
mkdirSync(S, { recursive: true })
const callId = process.env.CALL_ID
const WEB = process.env.WEB_URL ?? 'http://localhost:3000'
const DOWNLOADS = `${S}/downloads`
rmSync(DOWNLOADS, { recursive: true, force: true })
const { proc, page } = await launch(9336, S)
const results = []
const check = (name, ok, detail = '') => results.push([ok ? 'PASS' : 'FAIL', name, detail])

async function waitForDownload(extension, timeout = 15000) {
  const end = Date.now() + timeout
  while (Date.now() < end) {
    const files = existsSync(DOWNLOADS) ? readdirSync(DOWNLOADS).filter(f => f.endsWith(extension)) : []
    if (files.length) return `${DOWNLOADS}/${files[0]}`
    await sleep(200)
  }
  throw new Error(`no ${extension} download`)
}

const inputValues = section => page.eval(`[...document.querySelectorAll('[data-section=${section}] .editable-item input[type=text]')].map(i => i.value)`)

try {
  await page.allowDownloads(DOWNLOADS)
  await page.resize(900)
  await page.goto(`${WEB}/calls/${callId}`)
  await page.waitFor("document.querySelector('[data-section=summary]')", 15000, 'draft shown')
  check('the finished draft offers Edit, Download Markdown and Download PDF', await page.eval("['Edit proposal', 'Download Markdown', 'Download PDF'].every(t => [...document.querySelectorAll('button')].some(b => b.textContent.includes(t)))"))
  await page.shot(`${S}/20-view-mode.png`)

  // --- editing
  await page.click('Edit proposal', 'button')
  await page.waitFor("document.querySelector('.editor')", 5000, 'editor')
  check('Save is disabled until something changes', await page.eval("[...document.querySelectorAll('button')].find(b => b.textContent.includes('Save changes')).disabled"))
  await page.shot(`${S}/21-editor.png`)

  await page.fill('[data-section=summary] textarea', 'Resumen revisado por la freelancer.')
  const before = await inputValues('scope')
  const billing = before.findIndex(v => v.includes('menú de facturación'))
  check('the sample draft has the "menú de facturación" slip to remove', billing >= 0, before.join(' | '))
  if (billing >= 0) {
    await page.eval(`document.querySelectorAll('[data-section=scope] .editable-item')[${billing}].querySelector('button[aria-label="Remove item"]').click()`)
  }
  await page.eval("[...document.querySelectorAll('[data-section=scope] button')].find(b => b.textContent.includes('Add item')).click()")
  await sleep(150)
  await page.eval(`(() => { const el = [...document.querySelectorAll('[data-section=scope] .editable-item input[type=text]')].pop()
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, 'Panel de administración'); el.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  const flag = await page.eval(`(() => { const row = [...document.querySelectorAll('[data-section=scope] .editable-item')].pop(); const cb = row.querySelector('input[type=checkbox]'); return { checked: cb.checked, disabled: cb.disabled, label: row.innerText } })()`)
  check('an item the user adds is flagged as an assumption and cannot be unflagged', flag.checked && flag.disabled, flag.label.replace(/\n/g, ' '))
  check('sourced items show their source chips in the editor', (await page.eval("document.querySelectorAll('[data-section=scope] .editable-item .chip').length")) > 0)
  await page.eval("document.querySelector('[data-section=scope] .editable-item .chip').click()")
  await page.waitFor("document.querySelector('[data-section=scope] .quote')", 3000, 'quote in editor')
  check('clicking a source in the editor shows the quote', true)
  await page.eval("document.querySelector('[data-section=scope] .quote .link').click()")
  await page.waitFor("document.querySelector('.transcript li.highlight')", 4000, 'highlight from editor')
  check('Show in transcript works from the editor too', true)
  check('Save is enabled after changes', !(await page.eval("[...document.querySelectorAll('button')].find(b => b.textContent.includes('Save changes')).disabled")))
  await page.shot(`${S}/22-editor-changed.png`)

  // --- rules
  await page.fill('[data-section=summary] textarea', 'El proyecto cuesta $5,000 en total.')
  await page.click('Save changes', 'button')
  await page.waitFor("document.body.innerText.includes('The summary never includes prices')", 6000, 'price refused')
  check('a price in the summary is refused with a clear message and stays in the editor', await page.eval("!!document.querySelector('.editor')"))
  await page.shot(`${S}/23-price-refused.png`)
  await page.fill('[data-section=summary] textarea', 'Resumen revisado por la freelancer.')

  // --- save
  await page.click('Save changes', 'button')
  await page.waitFor("document.body.innerText.includes('Changes saved.')", 8000, 'saved')
  const summary = await page.eval("document.querySelector('[data-section=summary] p').textContent")
  const scope = await page.eval("[...document.querySelectorAll('[data-section=scope] .draft-item')].map(li => li.innerText.replace(/\\n/g, ' '))")
  check('the saved summary is shown', summary === 'Resumen revisado por la freelancer.')
  check('the removed item is gone and the new one is labelled', !scope.some(t => t.includes('menú de facturación')) && scope.some(t => t.includes('Panel de administración') && t.includes('Assumption')), scope.join(' | '))
  await page.shot(`${S}/24-saved.png`)

  await page.goto(`${WEB}/calls/${callId}`)
  await page.waitFor("document.querySelector('[data-section=summary]')", 15000, 'reloaded')
  check('the edits survive a reload', (await page.eval("document.querySelector('[data-section=summary] p').textContent")) === 'Resumen revisado por la freelancer.')

  // --- unsaved changes guard
  await page.click('Edit proposal', 'button')
  await page.waitFor("document.querySelector('.editor')", 5000)
  await page.fill('[data-section=summary] textarea', 'Cambio sin guardar')
  const dialogsBefore = page.dialogs.length
  await page.click('Calls', 'nav a')
  await sleep(800)
  check('leaving with unsaved changes asks first', page.dialogs.length > dialogsBefore && /unsaved changes/i.test(page.dialogs.at(-1)), page.dialogs.at(-1))
  await page.goto(`${WEB}/calls/${callId}`)
  await page.waitFor("document.querySelector('[data-section=summary]')", 15000)
  check('the unsaved change was not kept', (await page.eval("document.querySelector('[data-section=summary] p').textContent")) === 'Resumen revisado por la freelancer.')

  // --- downloads
  await page.click('Download Markdown', 'button')
  const md = readFileSync(await waitForDownload('.md'), 'utf8')
  check('the Markdown download has the edits and the assumption label', md.includes('Resumen revisado por la freelancer.') && md.includes('Panel de administración (por confirmar)') && !md.includes('menú de facturación'), md.split('\n').slice(0, 6).join(' | '))
  check('the Markdown has no timestamps or quotes from the call', !/\b\d{1,2}:\d{2}\b/.test(md) && !md.includes('“'))
  check('the Markdown has the profile\'s rates and terms', md.includes('650 MXN por hora') && md.includes('50% de anticipo y 50% a la entrega.'))
  await page.click('Download PDF', 'button')
  const pdf = readFileSync(await waitForDownload('.pdf'))
  check('downloads are named by the api (not the fallback)', readdirSync(DOWNLOADS).every(f => f.startsWith('propuesta-')), readdirSync(DOWNLOADS).join(', '))
  check('the PDF download is a PDF', pdf.subarray(0, 5).toString() === '%PDF-', `${pdf.length} bytes`)
  console.log('files:', readdirSync(DOWNLOADS).join(', '))

  // --- a refused export shows a message, not raw JSON
  await page.click('Edit proposal', 'button')
  await page.waitFor("document.querySelector('.editor')", 5000)
  await page.fill('[data-section=summary] textarea', 'Zażółć gęślą jaźń: texto que el PDF no puede dibujar.')
  await page.click('Save changes', 'button')
  await page.waitFor("document.body.innerText.includes('Changes saved.')", 8000)
  await page.click('Download PDF', 'button')
  await page.waitFor("document.body.innerText.includes('Export it as Markdown instead')", 8000, 'pdf refusal message')
  check('a PDF that cannot be drawn is refused with a plain message in the page', !(await page.text()).includes('{"detail"'))
  await page.shot(`${S}/25-pdf-refused.png`)

  // --- phone width
  await page.click('Edit proposal', 'button')
  await page.waitFor("document.querySelector('.editor')", 5000)
  await page.resize(390, 800)
  await sleep(300)
  check('the editor has no horizontal scroll on a phone-width screen', !(await page.eval('document.documentElement.scrollWidth > document.documentElement.clientWidth')))
  await page.shot(`${S}/26-editor-mobile.png`)
} catch (e) {
  results.push(['FAIL', 'script error', String(e.message)])
} finally {
  console.log(results.map(r => r.join(' | ')).join('\n'))
  console.log('browser console problems:', JSON.stringify(page.logs.slice(0, 8)))
  proc.kill()
}
