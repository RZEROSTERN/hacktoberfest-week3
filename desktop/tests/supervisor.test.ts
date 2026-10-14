import fs from 'node:fs'
import path from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { Service, Supervisor } from '../src/supervisor'
import { alive, fakeService, tempDir, until } from './helpers'

const services: Service[] = []
function track(service: Service): Service {
  services.push(service)
  return service
}
afterEach(async () => {
  await Promise.all(services.splice(0).map(service => service.stop()))
})

describe('Service', () => {
  it('waits until the health check answers', async () => {
    const dir = tempDir()
    const service = track(new Service(await fakeService(dir, 'api'), { onFatal: () => {} }))
    await service.start()
    expect(service.pid).toBeGreaterThan(0)
    expect(alive(service.pid!)).toBe(true)
  })

  it('fails with a clear message when the process dies while starting, and does not restart it', async () => {
    const dir = tempDir()
    const log = path.join(dir, 'starts.log')
    const fatal: string[] = []
    const service = track(
      new Service(await fakeService(dir, 'api', { EXIT_AT_START: '1', START_LOG: log }), {
        onFatal: (_name, reason) => fatal.push(reason),
      }),
    )
    await expect(service.start()).rejects.toThrow(/api stopped while starting/)
    await new Promise(resolve => setTimeout(resolve, 500))
    expect(fs.readFileSync(log, 'utf8').trim().split('\n')).toHaveLength(1)
    expect(fatal).toEqual([])
  })

  it('gives up and stops the process when it never answers', async () => {
    const dir = tempDir()
    const spec = await fakeService(dir, 'api', { NEVER_READY: '1' }, { startTimeoutMs: 700 })
    const service = track(new Service(spec, { onFatal: () => {} }))
    await expect(service.start()).rejects.toThrow(/did not answer within/)
    expect(service.pid).toBeUndefined()
  })

  it('reports a program that cannot be launched', async () => {
    const dir = tempDir()
    const spec = await fakeService(dir, 'api', {}, { command: path.join(dir, 'missing-binary') })
    const service = track(new Service(spec, { onFatal: () => {} }))
    await expect(service.start()).rejects.toThrow(/api could not be started/)
  })

  it('restarts a crashed service once, then reports it as fatal', async () => {
    const dir = tempDir()
    const log = path.join(dir, 'starts.log')
    const fatal: string[] = []
    const service = track(
      new Service(await fakeService(dir, 'api', { CRASH_AFTER_MS: '700', START_LOG: log }), {
        onFatal: (name, reason) => fatal.push(`${name}: ${reason}`),
      }),
    )
    await service.start()
    await until(() => fatal.length > 0, 12000)
    expect(fs.readFileSync(log, 'utf8').trim().split('\n')).toHaveLength(2) // the start and one restart
    expect(fatal[0]).toMatch(/^api: api stopped unexpectedly/)
  })

  it('stops the whole process group, helpers included', async () => {
    const dir = tempDir()
    const helperFile = path.join(dir, 'helper.pid')
    const service = track(new Service(await fakeService(dir, 'ollama', { CHILD_PID_FILE: helperFile }), { onFatal: () => {} }))
    await service.start()
    const helper = Number(fs.readFileSync(helperFile, 'utf8'))
    const leader = service.pid!
    expect(alive(helper)).toBe(true)
    await service.stop()
    await until(() => !alive(helper) && !alive(leader))
  })

  it('does not report a deliberate stop as a crash', async () => {
    const dir = tempDir()
    const fatal: string[] = []
    const service = track(new Service(await fakeService(dir, 'api'), { onFatal: (name) => fatal.push(name) }))
    await service.start()
    await service.stop()
    await new Promise(resolve => setTimeout(resolve, 400))
    expect(fatal).toEqual([])
  })

  it('records its pid for cleanup after a hard kill and forgets it on stop', async () => {
    const dir = tempDir()
    const pidFile = path.join(dir, 'services.json')
    const service = track(new Service(await fakeService(dir, 'api', {}, { pidFile }), { onFatal: () => {} }))
    await service.start()
    expect(JSON.parse(fs.readFileSync(pidFile, 'utf8')).api.pid).toBe(service.pid)
    await service.stop()
    await until(() => !fs.existsSync(pidFile))
  })
})

describe('Supervisor', () => {
  it('starts services in order and stops them in reverse order', async () => {
    const dir = tempDir()
    const log = path.join(dir, 'order.log')
    const first = track(new Service(await fakeService(dir, 'ollama', { START_LOG: log }), { onFatal: () => {} }))
    const second = track(new Service(await fakeService(dir, 'api', { START_LOG: log }), { onFatal: () => {} }))
    const supervisor = new Supervisor()
    await supervisor.startAll([first, second])
    expect(fs.readFileSync(log, 'utf8').trim().split('\n')).toEqual(['ollama', 'api'])
    const pids = [first.pid!, second.pid!]
    await supervisor.stopAll()
    await until(() => pids.every(pid => !alive(pid)))
  })

  it('does not start the next service when the first one fails', async () => {
    const dir = tempDir()
    const log = path.join(dir, 'order.log')
    const first = track(new Service(await fakeService(dir, 'ollama', { EXIT_AT_START: '1', START_LOG: log }), { onFatal: () => {} }))
    const second = track(new Service(await fakeService(dir, 'api', { START_LOG: log }), { onFatal: () => {} }))
    await expect(new Supervisor().startAll([first, second])).rejects.toThrow()
    expect(fs.readFileSync(log, 'utf8').trim().split('\n')).toEqual(['ollama'])
  })
})
