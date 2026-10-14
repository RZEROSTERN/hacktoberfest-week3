import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { contentSecurityPolicy, inlineScriptHashes, resolveAsset, serve } from '../src/protocol'
import { tempDir } from './helpers'

const API = 'http://127.0.0.1:5555'

function site(): string {
  const root = tempDir()
  const files: Record<string, string> = {
    'index.html': '<h1>home</h1>',
    '200.html': '<h1>spa</h1><script>var a=1</script>',
    '404.html': '<h1>nope</h1>',
    'profile/index.html': '<h1>profile</h1>',
    '_nuxt/app.js': 'console.log(1)',
    '_nuxt/style.css': 'a{}',
  }
  for (const [name, text] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(root, name)), { recursive: true })
    fs.writeFileSync(path.join(root, name), text)
  }
  fs.writeFileSync(path.join(path.dirname(root), 'secret.txt'), 'outside')
  return root
}

describe('resolveAsset', () => {
  const root = site()

  it('serves files, folders and the home page', () => {
    expect(resolveAsset(root, '/')).toBe(path.join(root, 'index.html'))
    expect(resolveAsset(root, '/profile')).toBe(path.join(root, 'profile', 'index.html'))
    expect(resolveAsset(root, '/_nuxt/app.js')).toBe(path.join(root, '_nuxt', 'app.js'))
  })

  it('gives routes that were not pre-rendered the single-page entry', () => {
    expect(resolveAsset(root, '/calls/abc123')).toBe(path.join(root, '200.html'))
  })

  it('keeps a missing asset a 404 instead of answering with a page', () => {
    expect(resolveAsset(root, '/_nuxt/missing.js')).toBeNull()
  })

  it('refuses to leave the web folder', () => {
    for (const evil of ['/../secret.txt', '/%2e%2e/secret.txt', '/..%2fsecret.txt', '/_nuxt/../../secret.txt', '/a%00b']) {
      const found = resolveAsset(root, evil)
      expect(found === null || found.startsWith(root + path.sep), evil).toBe(true)
      expect(found, evil).not.toBe(path.join(path.dirname(root), 'secret.txt'))
    }
    expect(resolveAsset(root, '/%E0%A4%A')).toBeNull() // malformed escape
  })
})

describe('content security policy', () => {
  it('allows exactly the inline scripts of the page, as hashes', () => {
    const html = [
      '<script type="importmap">{"imports":{}}</script>',
      '<script type="module" src="/_nuxt/a.js"></script>',
      '<script>window.x = 1</script>',
      '<script type="application/json" id="__NUXT_DATA__">[1]</script>',
    ].join('')
    const hash = (text: string) => `'sha256-${crypto.createHash('sha256').update(text).digest('base64')}'`
    expect(inlineScriptHashes(html)).toEqual([hash('{"imports":{}}'), hash('window.x = 1')])
  })

  it('never lets the page reach anything but itself and the local api', () => {
    const policy = contentSecurityPolicy('<script>1</script>', API)
    expect(policy).toContain("default-src 'none'")
    expect(policy).toContain(`connect-src 'self' ${API}`)
    expect(policy).not.toContain('unsafe-eval')
    expect(policy).not.toMatch(/script-src[^;]*unsafe-inline/)
    expect(policy).not.toMatch(/https?:\/\/(?!127\.0\.0\.1)/)
  })
})

describe('serve', () => {
  const root = site()

  it('answers with the right type and a policy on pages', () => {
    const page = serve(root, 'app://postcall/', API)
    expect(page.status).toBe(200)
    expect(page.headers['content-type']).toBe('text/html; charset=utf-8')
    expect(page.headers['content-security-policy']).toContain(API)
    const script = serve(root, 'app://postcall/_nuxt/app.js', API)
    expect(script.headers['content-type']).toBe('text/javascript; charset=utf-8')
    expect(script.headers['content-security-policy']).toBeUndefined()
  })

  it('refuses another host or scheme', () => {
    expect(serve(root, 'app://evil/', API).status).toBe(404)
    expect(serve(root, 'https://postcall/', API).status).toBe(404)
  })
})
