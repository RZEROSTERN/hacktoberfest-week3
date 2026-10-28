import { spawn, type ChildProcess } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { forgetService, recordService } from './pidfile'
import { killTree, spawnOptions } from './processes'

export interface ServiceSpec {
  name: string
  command: string
  args?: string[]
  env: Record<string, string>
  healthUrl: string
  logFile: string
  startTimeoutMs: number
  /** Where the pid is recorded, so a later start can clean up after a hard kill. */
  pidFile?: string
}

export interface Handlers {
  /** The service died more often than allowed (or could not be started again). */
  onFatal: (service: string, reason: string) => void
}

const STOP_GRACE_MS = 8000

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function healthy(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(1500) })
    return response.ok
  } catch {
    return false
  }
}

/** One background program: started, watched, restarted once if it crashes, stopped on quit. */
export class Service {
  private child: ChildProcess | null = null
  private exited: Promise<void> = Promise.resolve()
  private stopping = false
  private launching = false
  private restarts = 0
  /** How many times the program died without being asked to, during this run of the app. */
  crashes = 0

  constructor(
    readonly spec: ServiceSpec,
    private readonly handlers: Handlers,
    private readonly maxRestarts = 1,
  ) {}

  get pid(): number | undefined {
    return this.child?.pid
  }

  async start(): Promise<void> {
    this.stopping = false
    this.restarts = 0
    await this.launch()
  }

  async stop(): Promise<void> {
    this.stopping = true
    const child = this.child
    if (!child?.pid) return
    killTree(child.pid, 'SIGTERM') // on Windows this already ends the whole tree
    const timedOut = await Promise.race([this.exited.then(() => false), sleep(STOP_GRACE_MS).then(() => true)])
    if (timedOut) {
      killTree(child.pid, 'SIGKILL')
      await this.exited
    }
  }

  private async launch(): Promise<void> {
    const { spec } = this
    fs.mkdirSync(path.dirname(spec.logFile), { recursive: true })
    const log = fs.openSync(spec.logFile, 'w') // a fresh log per start; it never holds call content
    this.launching = true
    let child: ChildProcess
    try {
      child = spawn(spec.command, spec.args ?? [], {
        env: spec.env,
        stdio: ['ignore', log, log],
        ...spawnOptions(), // its own process group on Unix; a hidden window on Windows
      })
    } finally {
      fs.closeSync(log)
    }
    this.child = child
    let spawnError: Error | null = null
    child.once('error', (error) => {
      spawnError = error
    })
    this.exited = new Promise((resolve) => {
      child.once('close', (code, signal) => {
        resolve()
        this.onExit(child, code, signal)
      })
    })
    if (spec.pidFile && child.pid) recordService(spec.pidFile, spec.name, child.pid, spec.command)

    try {
      await this.waitHealthy(child, () => spawnError)
    } catch (error) {
      await this.stop()
      throw error
    } finally {
      this.launching = false
    }
  }

  private async waitHealthy(child: ChildProcess, failure: () => Error | null): Promise<void> {
    const deadline = Date.now() + this.spec.startTimeoutMs
    while (Date.now() < deadline) {
      const error = failure()
      if (error) throw new Error(`${this.spec.name} could not be started: ${error.message}`)
      if (child.exitCode !== null || child.signalCode !== null) {
        throw new Error(`${this.spec.name} stopped while starting (${child.exitCode ?? child.signalCode})`)
      }
      if (await healthy(this.spec.healthUrl)) return
      await sleep(200)
    }
    throw new Error(`${this.spec.name} did not answer within ${Math.round(this.spec.startTimeoutMs / 1000)} s`)
  }

  private onExit(child: ChildProcess, code: number | null, signal: NodeJS.Signals | null): void {
    if (this.child !== child) return
    if (child.pid) killTree(child.pid, 'SIGKILL') // helpers (llama-server, whisper-cli) must not outlive it
    this.child = null
    if (this.spec.pidFile) forgetService(this.spec.pidFile, this.spec.name)
    if (this.stopping || this.launching) return // a deliberate stop, or start() reports the failure itself
    this.crashes += 1
    const reason = `${this.spec.name} stopped unexpectedly (${code ?? signal})`
    if (this.restarts >= this.maxRestarts) {
      this.handlers.onFatal(this.spec.name, reason)
      return
    }
    this.restarts += 1
    this.launch().catch((error: Error) => this.handlers.onFatal(this.spec.name, error.message))
  }
}

/** Starts services in order and stops them in reverse order. */
export class Supervisor {
  private started: Service[] = []

  async startAll(services: Service[]): Promise<void> {
    for (const service of services) {
      await service.start()
      this.started.push(service)
    }
  }

  /** Stops everything. Returns whether any program had crashed meanwhile, in which case helpers it started may be left over. */
  async stopAll(): Promise<boolean> {
    const toStop = [...this.started].reverse()
    this.started = []
    const crashed = toStop.some(service => service.crashes > 0)
    for (const service of toStop) await service.stop()
    return crashed
  }
}
