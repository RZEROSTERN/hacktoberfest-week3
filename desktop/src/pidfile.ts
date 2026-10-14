import { execFileSync } from 'node:child_process'
import fs from 'node:fs'

type Entries = Record<string, { pid: number; command: string }>

function read(file: string): Entries {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8')) as Entries
  } catch {
    return {}
  }
}

function write(file: string, entries: Entries): void {
  if (Object.keys(entries).length === 0) fs.rmSync(file, { force: true })
  else fs.writeFileSync(file, JSON.stringify(entries))
}

export function recordService(file: string, name: string, pid: number, command: string): void {
  write(file, { ...read(file), [name]: { pid, command } })
}

export function forgetService(file: string, name: string): void {
  const entries = read(file)
  delete entries[name]
  write(file, entries)
}

/** The command line of a running process, or null when there is none with that pid. */
export function commandOf(pid: number): string | null {
  try {
    return execFileSync('ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' }).trim() || null
  } catch {
    return null
  }
}

function killGroup(pid: number, signal: NodeJS.Signals): void {
  try {
    process.kill(-pid, signal)
  } catch {
    // the group is already gone
  }
}

/**
 * After a hard kill of the app (power loss, force quit) the services it started can still be running.
 * Stop the ones left in the pid file, but only when the pid still belongs to the same program, so a
 * recycled pid is never touched.
 */
export async function reapOrphans(
  file: string,
  lookup: (pid: number) => string | null = commandOf,
  graceMs = 2000,
): Promise<string[]> {
  const entries = read(file)
  const reaped: string[] = []
  for (const [name, { pid, command }] of Object.entries(entries)) {
    if (lookup(pid)?.includes(command)) {
      killGroup(pid, 'SIGTERM')
      reaped.push(name)
    }
  }
  if (reaped.length > 0) {
    await new Promise(resolve => setTimeout(resolve, graceMs))
    for (const name of reaped) {
      const entry = entries[name]
      if (entry && lookup(entry.pid)?.includes(entry.command)) killGroup(entry.pid, 'SIGKILL')
    }
  }
  fs.rmSync(file, { force: true })
  return reaped
}
