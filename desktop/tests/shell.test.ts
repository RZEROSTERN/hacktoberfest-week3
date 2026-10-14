import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { apiEnv, ollamaEnv } from '../src/env'
import { dataDirs, resolveLayout } from '../src/layout'
import { twoFreePorts } from '../src/ports'
import { isAllowedExternal, isAllowedRequest, isAppUrl } from '../src/security'

const dirs = dataDirs('/u/Scopewise')
const layout = resolveLayout({ packaged: true, resourcesPath: '/App/Contents/Resources', appRoot: '/ignored' })
const ports = { ollama: 41000, api: 41001 }

describe('layout', () => {
  it('finds the bundled programs next to the app when packaged', () => {
    expect(layout.ollamaBinary).toBe('/App/Contents/Resources/ollama/ollama')
    expect(layout.apiBinary).toBe('/App/Contents/Resources/api/scopewise-api')
    expect(layout.whisperBinary).toBe('/App/Contents/Resources/whisper/whisper-cli')
    expect(layout.webRoot).toBe('/App/Contents/Resources/web')
  })

  it('uses the build folders when run from the repository', () => {
    const dev = resolveLayout({ packaged: false, resourcesPath: '/x', appRoot: '/repo/desktop' })
    expect(dev.ollamaBinary).toBe('/repo/desktop/build/ollama/ollama')
    expect(dev.webRoot).toBe(path.join('/repo', 'web', '.output', 'public'))
  })

  it('keeps everything the app writes inside its user data folder', () => {
    for (const dir of Object.values(dirs)) expect(dir.startsWith('/u/Scopewise/')).toBe(true)
  })
})

describe('service environments', () => {
  const hostile = {
    PATH: '/usr/bin',
    OLLAMA_HOST: '0.0.0.0:11434',
    OLLAMA_MODELS: '/elsewhere',
    SCOPEWISE_LLM_MODEL: 'something:else',
    HOME: '/Users/someone',
    OPENAI_API_KEY: 'sk-secret',
  }

  it('binds the bundled Ollama to loopback with its own folders and without cloud models', () => {
    const env = ollamaEnv(ports, dirs, hostile)
    expect(env).toMatchObject({
      OLLAMA_HOST: '127.0.0.1:41000',
      OLLAMA_MODELS: '/u/Scopewise/models/ollama',
      OLLAMA_NO_CLOUD: '1',
      HOME: '/u/Scopewise/ollama-home',
      PATH: '/usr/bin',
    })
    expect(env).not.toHaveProperty('OPENAI_API_KEY')
  })

  it('points the api at the bundled Ollama and lets it follow the app', () => {
    const env = apiEnv(ports, dirs, layout, 777, hostile)
    expect(env).toMatchObject({
      SCOPEWISE_HOST: '127.0.0.1',
      SCOPEWISE_PORT: '41001',
      SCOPEWISE_OLLAMA_URL: 'http://127.0.0.1:41000',
      SCOPEWISE_DATA_DIR: '/u/Scopewise/data',
      SCOPEWISE_MODELS_DIR: '/u/Scopewise/models',
      SCOPEWISE_CORS_ORIGINS: '["app://scopewise"]',
      SCOPEWISE_WHISPER_CLI: '/App/Contents/Resources/whisper/whisper-cli',
      SCOPEWISE_PARENT_PID: '777',
    })
    expect(env).not.toHaveProperty('SCOPEWISE_LLM_MODEL') // the model always comes from the settings
    expect(env.HOME).toBeUndefined()
  })
})

describe('ports', () => {
  it('picks two different free ports', async () => {
    const [a, b] = await twoFreePorts()
    expect(a).not.toBe(b)
    expect(a).toBeGreaterThan(1023)
  })
})

describe('security rules', () => {
  it('only treats its own origin as the app', () => {
    expect(isAppUrl('app://scopewise/calls/1')).toBe(true)
    expect(isAppUrl('app://other/')).toBe(false)
    expect(isAppUrl('https://scopewise/')).toBe(false)
    expect(isAppUrl('not a url')).toBe(false)
  })

  it('opens only the Ollama library in the browser', () => {
    expect(isAllowedExternal('https://ollama.com/library')).toBe(true)
    expect(isAllowedExternal('http://ollama.com/library')).toBe(false)
    expect(isAllowedExternal('https://ollama.com.evil.example/')).toBe(false)
    expect(isAllowedExternal('file:///etc/passwd')).toBe(false)
  })

  it('cancels every request that is not the app, the local api or the start page', () => {
    const api = 'http://127.0.0.1:41001'
    expect(isAllowedRequest('app://scopewise/_nuxt/a.js', api)).toBe(true)
    expect(isAllowedRequest('http://127.0.0.1:41001/health', api)).toBe(true)
    expect(isAllowedRequest('data:text/html,hi', api)).toBe(true)
    expect(isAllowedRequest('http://127.0.0.1:41000/api/tags', api)).toBe(false) // Ollama is for the api only
    expect(isAllowedRequest('https://example.com/x.js', api)).toBe(false)
    expect(isAllowedRequest('file:///etc/passwd', api)).toBe(false)
  })
})
