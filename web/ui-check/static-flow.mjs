// The production static build served with an SPA fallback on WEB_URL (the way the desktop shell will load it).
import { mkdirSync } from 'node:fs'
import { launch } from './cdp.mjs'
const S = process.env.UI_OUT ?? new URL('../../.dev/ui-check', import.meta.url).pathname
mkdirSync(S, { recursive: true })
const callId = process.env.CALL_ID
const WEB = process.env.WEB_URL ?? 'http://localhost:3000'
const { proc, page } = await launch(9335, S)
const results = []
const check = (n, ok, d = '') => results.push([ok ? 'PASS' : 'FAIL', n, d])
try {
  await page.resize(900)
  await page.goto(`${WEB}/`)
  await page.waitFor("document.querySelector('.calls')", 15000, 'home')
  check('production build: home lists the call', (await page.text()).includes('interview.mp3'))
  check('production build: client-side navigation works', await page.click('Profile', 'nav a'))
  await page.waitFor("document.querySelector('form input[type=text]') && document.querySelector('form input[type=text]').value !== ''", 8000, 'profile via link')
  check('production build: profile loads after navigating', true)
  await page.goto(`${WEB}/calls/${callId}`, "document.querySelector('main h1')")
  await page.waitFor("document.body.innerText.includes('Proposal draft') && document.querySelector('[data-section=summary]')", 15000, 'deep link with draft')
  check('production build: a deep link loads and shows the saved draft', true)
  await page.goto(`${WEB}/new`)
  check('production build: another deep link works', (await page.text()).includes('every participant agreed'))
} catch (e) { results.push(['FAIL', 'script error', String(e.message)]) }
finally { console.log(results.map(r => r.join(' | ')).join('\n')); console.log('console problems:', JSON.stringify(page.logs.slice(0, 6))); proc.kill() }
