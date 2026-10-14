import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { parse } from '@vue/compiler-sfc'
import { describe, expect, it } from 'vitest'
import { DEFAULT_LOCALE, LOCALES, isLocale, localeInfo, resolveLocale } from '../app/i18n/locales'
import { SECTION_IDS } from '../app/utils/sections'

const APP = path.resolve(__dirname, '../app')
const REPO = path.resolve(__dirname, '../..')

type Messages = { [key: string]: string | Messages }

const load = (code: string): Messages => JSON.parse(readFileSync(path.join(APP, 'locales', `${code}.json`), 'utf8'))
const en = load('en')

function flatten(messages: Messages, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(messages)) {
    if (typeof value === 'string') out[prefix + key] = value
    else Object.assign(out, flatten(value, `${prefix}${key}.`))
  }
  return out
}
const english = flatten(en)

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'locales' ? [] : sourceFiles(full)
    return /\.(vue|ts)$/.test(entry.name) ? [full] : []
  })
}

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map(m => m[1]!).sort()

describe('the language list', () => {
  it('has the eleven languages, English first, and only Arabic runs right to left', () => {
    expect(LOCALES.map(l => l.code)).toEqual(['en', 'es', 'fr', 'pt', 'ja', 'de', 'ru', 'it', 'hi', 'zh', 'ar'])
    expect(LOCALES.filter(l => l.dir === 'rtl').map(l => l.code)).toEqual(['ar'])
    expect(localeInfo('zh').htmlLang).toBe('zh-Hans')
    expect(isLocale('xx')).toBe(false)
  })
})

describe('resolveLocale', () => {
  it('takes the first preferred language the app speaks, by its main part', () => {
    expect(resolveLocale(['pt-BR', 'en'])).toBe('pt')
    expect(resolveLocale(['en-GB'])).toBe('en')
    expect(resolveLocale(['zh-TW', 'en'])).toBe('zh')
    expect(resolveLocale(['ZH_cn'])).toBe('zh')
    expect(resolveLocale(['ko-KR', 'ar-EG', 'en'])).toBe('ar')
    expect(resolveLocale([null, undefined, 'de'])).toBe('de')
  })

  it('falls back to English when nothing matches', () => {
    expect(resolveLocale(['ko', 'th'])).toBe(DEFAULT_LOCALE)
    expect(resolveLocale([])).toBe(DEFAULT_LOCALE)
  })
})

describe('the translation files', () => {
  it.each(LOCALES.map(l => l.code))('%s has every message English has, with the same values to fill in', (code) => {
    const messages = flatten(load(code))
    expect(Object.keys(messages).sort()).toEqual(Object.keys(english).sort())
    for (const [key, value] of Object.entries(messages)) {
      expect(value.trim(), `${code}: ${key} is empty`).not.toBe('')
      expect(placeholders(value), `${code}: ${key}`).toEqual(placeholders(english[key]!))
    }
  })

  it.each(LOCALES.map(l => l.code))('%s has no character the message format treats as syntax', (code) => {
    for (const [key, value] of Object.entries(flatten(load(code)))) {
      // `|` separates plural forms and `@` links messages; braces are only for {values}.
      expect(value, `${code}: ${key}`).not.toMatch(/[|@]/)
      expect(value.replace(/\{\w+\}/g, ''), `${code}: ${key}`).not.toMatch(/[{}]/)
    }
  })

  it('keeps the brand name in every language', () => {
    for (const { code } of LOCALES) {
      expect(flatten(load(code))['setup.request.title'], code).toContain('PostCall')
    }
  })
})

describe('what the code asks for exists', () => {
  const used = new Set<string>()
  for (const file of sourceFiles(APP)) {
    const text = readFileSync(file, 'utf8')
    for (const match of text.matchAll(/(?:\$t|\bt|errors\.message|format\.t)\(\s*['"`]([^'"`$]+)['"`]/g)) used.add(match[1]!)
    for (const match of text.matchAll(/keypath="([^"]+)"/g)) used.add(match[1]!)
    for (const match of text.matchAll(/'(errors\.[A-Za-z]+)'/g)) used.add(match[1]!)
  }

  it('has an English message for every key used in the source', () => {
    expect(used.size).toBeGreaterThan(150) // the scan is finding the calls
    expect([...used].filter(key => !(key in english))).toEqual([])
  })

  it('has a message for every case of the keys built at run time', () => {
    const wanted = [
      ...['queued', 'converting', 'transcribing', 'done', 'failed', 'cancelled'].map(s => `status.${s}`),
      ...['queued', 'extracting', 'extractingParts', 'drafting', 'done', 'failed', 'cancelled'].map(s => `draftStatus.${s}`),
      ...SECTION_IDS.map(id => `sections.${id}`),
      ...['client_context', 'problem', 'goals', 'requirements', 'constraints', 'budget', 'deadlines', 'next_steps', 'risks'].map(g => `notes.groups.${g}`),
      ...['engine', 'llm', 'whisper', 'verify', 'compat', 'ready'].map(s => `setup.steps.${s}`),
    ]
    expect(wanted.filter(key => !(key in english))).toEqual([])
  })

  it('translates every error code the api can answer with, in English exactly as the api says it', () => {
    const source = readFileSync(path.join(REPO, 'api/app/errors.py'), 'utf8')
    const table = source.slice(source.indexOf('ERROR_MESSAGES = {'), source.indexOf('class ApiError'))
    const codes = [...table.matchAll(/^ {4}"([a-z_]+)":/gm)].map(m => m[1]!)
    expect(codes.length).toBeGreaterThan(50)
    expect(codes.filter(code => !(`apiErrors.${code}` in english))).toEqual([])
  })

  it('describes each tested model as the api catalogue does, so the two cannot drift apart', () => {
    const catalogue = JSON.parse(readFileSync(path.join(REPO, 'api/data/models.json'), 'utf8')) as {
      llm: { model: string, note: string }[]
      whisper: { note: string }
    }
    for (const { model, note } of catalogue.llm) {
      expect(english[`models.${model.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')}.note`], model).toBe(note)
    }
    expect(english['models.whisper.note']).toBe(catalogue.whisper.note)
  })
})

describe('the templates', () => {
  // Words a template may write itself: the product name. Everything else a person reads is a message.
  const ALLOWED = new Set(['PostCall'])
  const TEXT_ATTRIBUTES = new Set(['aria-label', 'title', 'placeholder', 'alt', 'label'])
  const hasWords = (text: string) => /\p{L}/u.test(text)

  type Node = { type: number, content?: unknown, name?: string, value?: { content: string }, props?: Node[], children?: Node[] }
  function problems(node: Node, found: string[]) {
    if (node.type === 2 && typeof node.content === 'string') {
      const text = node.content.trim()
      if (text && hasWords(text) && !ALLOWED.has(text)) found.push(`text “${text}”`)
    }
    if (node.type === 1) {
      for (const prop of node.props ?? []) {
        if (prop.type === 6 && TEXT_ATTRIBUTES.has(prop.name ?? '') && prop.value?.content.trim()) {
          found.push(`${prop.name}="${prop.value.content}"`)
        }
      }
    }
    for (const child of node.children ?? []) problems(child, found)
  }

  it('contain no text a person reads that is not a message', () => {
    const offenders: string[] = []
    for (const file of sourceFiles(APP).filter(f => f.endsWith('.vue'))) {
      const { descriptor } = parse(readFileSync(file, 'utf8'))
      const found: string[] = []
      if (descriptor.template?.ast) problems(descriptor.template.ast as unknown as Node, found)
      offenders.push(...found.map(f => `${path.relative(APP, file)}: ${f}`))
    }
    expect(offenders).toEqual([])
  })
})
