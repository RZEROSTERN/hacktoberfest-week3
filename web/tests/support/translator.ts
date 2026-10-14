import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import type { Translate } from '../../app/utils/intl'

type Messages = { [key: string]: string | Messages }

function lookup(messages: Messages, key: string): string | undefined {
  let node: string | Messages | undefined = messages
  for (const part of key.split('.')) {
    if (typeof node !== 'object' || node === undefined) return undefined
    node = node[part]
  }
  return typeof node === 'string' ? node : undefined
}

/** A translator over the real message files, filling in `{values}` the way vue-i18n does. Throws on a missing key. */
export function translator(code = 'en'): Translate {
  const file = (c: string) => path.resolve(__dirname, `../../app/locales/${c}.json`)
  const messages: Messages = JSON.parse(readFileSync(file(code), 'utf8'))
  const english: Messages = JSON.parse(readFileSync(file('en'), 'utf8'))
  return (key, named = {}) => {
    const text = lookup(messages, key) ?? lookup(english, key)
    if (text === undefined) throw new Error(`no message for ${key}`)
    return text.replace(/\{(\w+)\}/g, (_, name: string) => String(named[name] ?? `{${name}}`))
  }
}

export const hasLocale = (code: string) => existsSync(path.resolve(__dirname, `../../app/locales/${code}.json`))
