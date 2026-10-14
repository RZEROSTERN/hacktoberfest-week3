import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import type { ServiceSpec } from '../src/supervisor'

export const FIXTURE = path.join(__dirname, 'fixtures', 'service.mjs')

export function tempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'scopewise-desktop-'))
}

export function freePort(): Promise<number> {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address() as net.AddressInfo
      server.close(() => resolve(port))
    })
  })
}

export function alive(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

export async function until(check: () => boolean, ms = 8000): Promise<void> {
  const deadline = Date.now() + ms
  while (!check()) {
    if (Date.now() > deadline) throw new Error('condition not met in time')
    await new Promise(resolve => setTimeout(resolve, 50))
  }
}

export async function fakeService(
  dir: string,
  name: string,
  extra: Record<string, string> = {},
  overrides: Partial<ServiceSpec> = {},
): Promise<ServiceSpec> {
  const port = await freePort()
  return {
    name,
    command: process.execPath,
    args: [FIXTURE],
    env: { PORT: String(port), NAME: name, ...extra },
    healthUrl: `http://127.0.0.1:${port}/health`,
    logFile: path.join(dir, `${name}.log`),
    startTimeoutMs: 5000,
    ...overrides,
  }
}
