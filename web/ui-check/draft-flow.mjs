// Draft, cancel, source links and transcript highlight with the real language model. Needs CALL_ID and a saved profile (run profile-flow first).
import { mkdirSync } from 'node:fs'
import { launch, sleep } from './cdp.mjs'
const S = process.env.UI_OUT ?? new URL('../../.dev/ui-check', import.meta.url).pathname
mkdirSync(S, { recursive: true })
const callId = process.env.CALL_ID
const WEB = process.env.WEB_URL ?? 'http://localhost:3000'
const { proc, page } = await launch(9334, S)
const results = []
const check = (name, ok, detail = '') => results.push([ok ? 'PASS' : 'FAIL', name, detail])
try {
  await page.resize(900)
  await page.goto(`${WEB}/calls/${callId}`)
  await page.waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.includes('Draft proposal'))", 15000, 'draft button')

  // A. start, see progress, cancel
  await page.click('Draft proposal', 'button')
  await page.waitFor("document.querySelector('.progress progress')", 10000, 'progress bar')
  let t = await page.text()
  check('progress is shown with a plain-language label', /Waiting to start|Reading the call|Writing the proposal/.test(t), t.match(/Waiting to start|Reading the call[^\n]*|Writing the proposal/)?.[0])
  await page.shot(`${S}/10-draft-progress.png`)
  await page.click('Cancel', 'button')
  await page.waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.includes('Cancelling'))", 4000, 'cancelling state')
  check('cancel gives immediate feedback ("Cancelling…")', true)
  const t0 = Date.now()
  await page.waitFor("document.body.innerText.includes('The draft was cancelled')", 120000, 'cancelled')
  check('the draft ends up cancelled', true, `${Math.round((Date.now() - t0) / 1000)} s after clicking Cancel`)
  await page.shot(`${S}/11-draft-cancelled.png`)

  // B. draft again, wait for the result
  check('after cancelling, the user can try again', await page.click('Try again', 'button'))
  const started = Date.now()
  await page.waitFor("document.querySelector('[data-section=scope]')", 240000, 'finished draft')
  check('the draft finishes', true, `${Math.round((Date.now() - started) / 1000)} s`)
  await sleep(500)
  t = await page.text()
  const titles = await page.eval("[...document.querySelectorAll('.proposal h3')].map(h => h.textContent.trim())")
  check('sections follow the profile (Out of scope unticked, Investment after Scope)', !titles.includes('Fuera de alcance') && titles.indexOf('Inversión') > titles.indexOf('Alcance'), titles.join(' > '))
  check('prices come from the profile', t.includes('650 MXN por hora') && t.includes('Sitio web de hasta 5 secciones: 24,000 MXN'))
  check('terms come from the profile', t.includes('50% de anticipo y 50% a la entrega.'))
  const summary = await page.eval("document.querySelector('[data-section=summary] p').textContent")
  check('the summary has no price', !/\$|MXN|\d{4,}/.test(summary), summary.slice(0, 80))
  await page.shot(`${S}/12-draft-done.png`)

  // C. source links
  const chipCount = await page.eval("document.querySelectorAll('[data-section=scope] .chip').length")
  check('scope items have source links', chipCount > 0, `${chipCount} chips`)
  await page.eval("document.querySelector('[data-section=scope] .chip').click()")
  await page.waitFor("document.querySelector('[data-section=scope] .quote')", 3000, 'quote panel')
  const quote = await page.eval("document.querySelector('[data-section=scope] .quote').innerText")
  check('clicking a source shows the quote and its time', /\d+:\d{2}/.test(quote) && quote.includes('“'), quote.replace(/\n/g, ' ').slice(0, 110))
  await page.shot(`${S}/13-source-quote.png`)
  await page.eval("[...document.querySelectorAll('[data-section=scope] .quote .link')][0].click()")
  await page.waitFor("document.querySelector('.transcript li.highlight')", 4000, 'highlight')
  const hl = await page.eval("({ id: document.querySelector('.transcript li.highlight').id, text: document.querySelector('.transcript li.highlight').innerText, open: document.querySelector('details[open] .transcript') !== null })")
  check('"Show in transcript" opens the transcript and highlights the cited segment', hl.open && hl.id.startsWith('segment-'), `${hl.id}: ${hl.text.replace(/\n/g, ' ').slice(0, 70)}`)
  check('the highlighted segment is the quoted one', quote.includes(hl.text.split('\n').slice(-1)[0].trim().slice(0, 25)))
  await page.shot(`${S}/14-transcript-highlight.png`)

  // D. notes, assumptions flag, mobile
  await page.eval("document.querySelector('details summary').click()")
  await page.shot(`${S}/15-notes-open.png`)
  await page.resize(390, 800)
  await sleep(300)
  check('the draft has no horizontal scroll on a phone-width screen', !(await page.eval('document.documentElement.scrollWidth > document.documentElement.clientWidth')))
  await page.shot(`${S}/16-draft-mobile.png`)
} catch (e) {
  results.push(['FAIL', 'script error', String(e.message)])
} finally {
  console.log(results.map(r => r.join(' | ')).join('\n'))
  console.log('browser console problems:', JSON.stringify(page.logs.slice(0, 8)))
  proc.kill()
}
