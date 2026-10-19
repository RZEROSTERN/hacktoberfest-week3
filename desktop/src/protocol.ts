import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { isAppUrl } from './security'

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
}

export function mimeFor(file: string): string {
  return MIME[path.extname(file).toLowerCase()] ?? 'application/octet-stream'
}

function isFile(file: string): boolean {
  try {
    return fs.statSync(file).isFile()
  } catch {
    return false
  }
}

/**
 * Map a request path of the generated web app to a file inside `root`, or null for "not found".
 * A page route that was not pre-rendered (like /calls/<id>) gets the SPA entry page, as a static
 * server would; a missing asset (anything with a file extension) stays a 404.
 */
export function resolveAsset(root: string, pathname: string): string | null {
  let decoded: string
  try {
    decoded = decodeURIComponent(pathname)
  } catch {
    return null
  }
  // No asset of the web app has these in its name. On Windows a backslash separates folders (`..\\` climbs
  // out of the root) and `:` opens drive letters and NTFS streams, so they are refused on every system.
  if (/[\0\\:]/.test(decoded)) return null
  const base = path.resolve(root)
  const target = path.resolve(base, `.${path.posix.normalize(`/${decoded}`)}`)
  if (target !== base && !target.startsWith(base + path.sep)) return null

  for (const candidate of [target, path.join(target, 'index.html')]) {
    if (isFile(candidate)) return candidate
  }
  if (path.extname(target) !== '') return null
  const entry = path.join(base, '200.html')
  return isFile(entry) ? entry : null
}

/** SHA-256 CSP sources for the page's own inline scripts (the import map and Nuxt's config). */
export function inlineScriptHashes(html: string): string[] {
  const hashes: string[] = []
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    const attributes = match[1] ?? ''
    if (/\bsrc\s*=/i.test(attributes)) continue
    if (/type\s*=\s*["']application\/json["']/i.test(attributes)) continue // data, not executable
    hashes.push(`'sha256-${crypto.createHash('sha256').update(match[2] ?? '').digest('base64')}'`)
  }
  return hashes
}

/** Everything the page may load: its own files and the local api. Nothing from the internet. */
export function contentSecurityPolicy(html: string, apiOrigin: string): string {
  return [
    "default-src 'none'",
    `script-src 'self' ${inlineScriptHashes(html).join(' ')}`.trim(),
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src 'self' ${apiOrigin}`,
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
  ].join('; ')
}

export interface Served {
  status: number
  headers: Record<string, string>
  body: Buffer | string
}

/** Pure part of the protocol handler, so it can be tested without Electron. */
export function serve(root: string, requestUrl: string, apiOrigin: string): Served {
  if (!isAppUrl(requestUrl)) return { status: 404, headers: {}, body: 'Not found' }
  const url = new URL(requestUrl)
  const file = resolveAsset(root, url.pathname)
  if (!file) return { status: 404, headers: { 'content-type': 'text/plain' }, body: 'Not found' }
  const body = fs.readFileSync(file)
  const headers: Record<string, string> = { 'content-type': mimeFor(file), 'cache-control': 'no-cache' }
  if (path.extname(file) === '.html') {
    headers['content-security-policy'] = contentSecurityPolicy(body.toString('utf8'), apiOrigin)
  }
  return { status: 200, headers, body }
}
