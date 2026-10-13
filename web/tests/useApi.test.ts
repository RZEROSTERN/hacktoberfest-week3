import { describe, expect, it } from 'vitest'
import { resolveApiBase } from '../app/composables/useApi'

describe('resolveApiBase', () => {
  it('prefers the desktop preload value', () => {
    expect(resolveApiBase('http://127.0.0.1:5123', 'http://127.0.0.1:8000')).toBe('http://127.0.0.1:5123')
  })

  it('falls back to runtimeConfig', () => {
    expect(resolveApiBase(undefined, 'http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000')
  })

  it('strips trailing slashes', () => {
    expect(resolveApiBase(undefined, 'http://127.0.0.1:8000/')).toBe('http://127.0.0.1:8000')
  })
})
