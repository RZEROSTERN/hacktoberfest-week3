// Profile, home, upload and call pages (no language model needed). Needs the dev api + web and CALL_ID of a finished call.
import { mkdirSync } from 'node:fs'
import { launch, sleep } from './cdp.mjs'
const S = process.env.UI_OUT ?? new URL('../../.dev/ui-check', import.meta.url).pathname
mkdirSync(S, { recursive: true })
const callId = process.env.CALL_ID
const WEB = process.env.WEB_URL ?? 'http://localhost:3000'
const { proc, page } = await launch(9333, S)
const results = []
const check = (name, ok, detail = '') => { results.push([ok ? 'PASS' : 'FAIL', name, detail]); }
try {
  await page.resize(900)

  await page.goto(`${WEB}/`)
  await page.waitFor("document.body.innerText.includes('No calls yet') || document.querySelector('.calls')", 15000, 'home loaded')
  await sleep(500)
  let t = await page.text()
  check('home shows the set-up-profile notice when there is no profile', t.includes('Set up your profile first'))
  await page.shot(`${S}/01-home-no-profile.png`)

  await page.goto(`${WEB}/profile`)
  await page.waitFor("document.querySelector('form')", 10000, 'profile form')
  await page.shot(`${S}/02-profile-empty.png`)
  check('save is disabled until a name is typed', await page.eval("document.querySelector('button[type=submit]').disabled"))

  await page.fill('form input[type=text]', 'Ana Pérez (Studio Demo)')                  // name
  await page.fill('form textarea', 'Sitios web\nSistemas de reservaciones')            // services (1st textarea)
  // hourly rate = 2nd text input, tone = 3rd
  const setNth = (sel, n, v) => page.eval(`(() => { const el = document.querySelectorAll(${JSON.stringify(sel)})[${n}]
      const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(v)}); el.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await setNth('form input[type=text]', 1, '650 MXN por hora')
  await setNth('form textarea', 1, 'Sitio web de hasta 5 secciones: 24,000 MXN')       // project rates
  await setNth('form textarea', 2, '50% de anticipo y 50% a la entrega.')              // payment terms
  await setNth('form input[type=text]', 2, 'profesional y cercano')                    // tone
  // Put "Investment" above "Scope" on purpose, then check the form keeps it below.
  const investmentUp = `(() => { const b = [...document.querySelectorAll('button')].find(x => x.getAttribute('aria-label') === 'Move Investment up'); b.click(); return true })()`
  for (let i = 0; i < 7; i++) { await page.eval(investmentUp); await sleep(60) }
  const order = await page.eval("[...document.querySelectorAll('.sections li label')].map(l => l.textContent.trim())")
  check('investment cannot be moved above scope', order.indexOf('Investment') > order.indexOf('Scope'), order.join(' > '))
  // Untick "Out of scope" to test section choice
  await page.eval(`(() => { const l = [...document.querySelectorAll('.sections li label')].find(x => x.textContent.trim() === 'Out of scope'); l.querySelector('input').click(); return true })()`)
  await page.shot(`${S}/03-profile-filled.png`)

  await page.click('Save profile', 'button')
  await page.waitFor("document.body.innerText.includes('Profile saved.')", 8000, 'saved confirmation')
  check('saving shows a confirmation', true)
  await page.shot(`${S}/04-profile-saved.png`)

  await page.goto(`${WEB}/profile`)
  await page.waitFor("document.querySelector('form') && document.querySelector('form input[type=text]').value !== ''", 8000, 'profile reloaded')
  check('the saved profile is loaded back', (await page.eval("document.querySelector('form input[type=text]').value")) === 'Ana Pérez (Studio Demo)')
  const sectionState = await page.eval("[...document.querySelectorAll('.sections li')].map(li => (li.querySelector('input').checked ? '[x] ' : '[ ] ') + li.querySelector('label').textContent.trim())")
  check('section choices persist (out of scope unticked)', sectionState.some(s => s.startsWith('[ ] Out of scope')), sectionState.join(' | '))

  await page.goto(`${WEB}/`)
  await page.waitFor("document.querySelector('.calls')", 10000, 'home with calls')
  t = await page.text()
  check('the notice is gone once a profile exists', !t.includes('Set up your profile first'))
  check('the call is listed with its status', t.includes('interview.mp3') && t.includes('Transcript ready'))
  await page.shot(`${S}/05-home-with-profile.png`)

  await page.goto(`${WEB}/new`)
  check('the new-proposal page shows the consent reminder', (await page.text()).includes('every participant agreed to be recorded'))
  await page.shot(`${S}/06-new.png`)

  await page.goto(`${WEB}/calls/${callId}`)
  await page.waitFor("document.body.innerText.includes('Proposal draft')", 10000, 'call page')
  t = await page.text()
  check('the call page offers to draft the proposal', t.includes('Draft proposal') && t.includes('Write it in'))
  check('the language defaults to the call language', t.includes('The language of the call (Spanish)'))
  await page.shot(`${S}/07-call-ready.png`)

  await page.resize(390, 800)
  await page.goto(`${WEB}/profile`)
  await page.waitFor("document.querySelector('form')", 8000)
  const overflow = await page.eval('document.documentElement.scrollWidth > document.documentElement.clientWidth')
  check('profile page has no horizontal scroll on a phone-width screen', !overflow)
  await page.shot(`${S}/08-profile-mobile.png`)
} catch (e) {
  results.push(['FAIL', 'script error', String(e.message)])
} finally {
  console.log(results.map(r => r.join(' | ')).join('\n'))
  console.log('browser console problems:', JSON.stringify(page.logs.slice(0, 8)))
  proc.kill()
}
