import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { commandOf, forgetService, reapOrphans, recordService } from '../src/pidfile'
import { alive, tempDir, until } from './helpers'

function leftover(): number {
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { detached: true, stdio: 'ignore' })
  child.unref()
  return child.pid!
}

describe('pid file', () => {
  it('records and forgets services', () => {
    const file = path.join(tempDir(), 'services.json')
    recordService(file, 'ollama', 11, '/a/ollama')
    recordService(file, 'api', 22, '/a/api')
    forgetService(file, 'ollama')
    expect(JSON.parse(fs.readFileSync(file, 'utf8'))).toEqual({ api: { pid: 22, command: '/a/api' } })
    forgetService(file, 'api')
    expect(fs.existsSync(file)).toBe(false)
  })

  it('stops a service left running by an app that was killed', async () => {
    const file = path.join(tempDir(), 'services.json')
    const pid = leftover()
    recordService(file, 'ollama', pid, process.execPath)
    expect(await reapOrphans(file, commandOf, 200)).toEqual(['ollama'])
    await until(() => !alive(pid))
    expect(fs.existsSync(file)).toBe(false)
  })

  it('never touches a pid that now belongs to another program', async () => {
    const file = path.join(tempDir(), 'services.json')
    const pid = leftover()
    recordService(file, 'ollama', pid, '/Applications/Scopewise.app/ollama')
    expect(await reapOrphans(file, commandOf, 200)).toEqual([])
    expect(alive(pid)).toBe(true)
    process.kill(-pid, 'SIGKILL')
  })

  it('does nothing when there is no file', async () => {
    expect(await reapOrphans(path.join(tempDir(), 'none.json'))).toEqual([])
  })
})
