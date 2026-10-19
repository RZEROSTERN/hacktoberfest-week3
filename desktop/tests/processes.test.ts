import { afterEach, describe, expect, it, vi } from 'vitest'
import { reapOrphans, recordService } from '../src/pidfile'
import { killTree, pidsRunningUnder, programOf, sameProgram, spawnOptions, sweepPrograms, type Runner } from '../src/processes'
import { tempDir } from './helpers'
import fs from 'node:fs'
import path from 'node:path'

afterEach(() => vi.restoreAllMocks())

/** A runner that records what it was asked to run and answers with canned text. */
function fakeRunner(answer = ''): { run: Runner; calls: Array<{ file: string; args: string[] }> } {
  const calls: Array<{ file: string; args: string[] }> = []
  return {
    calls,
    run: (file, args) => {
      calls.push({ file, args })
      return answer
    },
  }
}

describe('spawnOptions', () => {
  it('gives each program its own process group on Unix', () => {
    expect(spawnOptions('darwin')).toEqual({ detached: true, windowsHide: true })
    expect(spawnOptions('linux')).toEqual({ detached: true, windowsHide: true })
  })

  it('does not detach on Windows, where it would open a console window, and hides the window', () => {
    expect(spawnOptions('win32')).toEqual({ detached: false, windowsHide: true })
  })
})

describe('killTree', () => {
  it('signals the whole process group on Unix', () => {
    const kill = vi.spyOn(process, 'kill').mockImplementation(() => true)
    killTree(4321, 'SIGTERM', 'linux')
    expect(kill).toHaveBeenCalledWith(-4321, 'SIGTERM')
  })

  it('ends the whole tree with taskkill /T /F on Windows, whatever the signal', () => {
    const kill = vi.spyOn(process, 'kill').mockImplementation(() => true)
    const { run, calls } = fakeRunner()
    killTree(4321, 'SIGTERM', 'win32', run)
    expect(calls).toEqual([{ file: 'taskkill', args: ['/PID', '4321', '/T', '/F'] }])
    expect(kill).not.toHaveBeenCalled()
  })

  it('does not fail when the program is already gone', () => {
    vi.spyOn(process, 'kill').mockImplementation(() => {
      throw new Error('ESRCH')
    })
    expect(() => killTree(1, 'SIGKILL', 'darwin')).not.toThrow()
    const failing: Runner = () => {
      throw new Error('ERROR: The process "1" not found.')
    }
    expect(() => killTree(1, 'SIGKILL', 'win32', failing)).not.toThrow()
  })
})

describe('programOf and sameProgram', () => {
  it('reads the program name from tasklist on Windows', () => {
    const { run, calls } = fakeRunner('"ollama.exe","1234","Console","1","52,000 K"\r\n')
    expect(programOf(1234, 'win32', run)).toBe('ollama.exe')
    expect(calls[0]).toEqual({ file: 'tasklist', args: ['/FI', 'PID eq 1234', '/FO', 'CSV', '/NH'] })
  })

  it('finds nothing when tasklist says no task matches, in any language', () => {
    expect(programOf(1, 'win32', fakeRunner('INFO: No tasks are running which match the specified criteria.').run)).toBeNull()
    expect(programOf(1, 'win32', fakeRunner('INFORMACIÓN: no hay tareas en ejecución.').run)).toBeNull()
  })

  it('reads the command line from ps elsewhere', () => {
    const { run, calls } = fakeRunner('/opt/PostCall/resources/ollama/bin/ollama serve\n')
    expect(programOf(9, 'linux', run)).toBe('/opt/PostCall/resources/ollama/bin/ollama serve')
    expect(calls[0]?.file).toBe('ps')
  })

  it('compares a Windows program by file name, ignoring case, and a Unix one by command line', () => {
    expect(sameProgram('OLLAMA.EXE', 'C:\\Apps\\PostCall\\resources\\ollama\\ollama.exe', 'win32')).toBe(true)
    expect(sameProgram('chrome.exe', 'C:\\Apps\\PostCall\\resources\\ollama\\ollama.exe', 'win32')).toBe(false)
    expect(sameProgram('/a/b/ollama serve', '/a/b/ollama', 'linux')).toBe(true)
    expect(sameProgram('/usr/bin/python', '/a/b/ollama', 'linux')).toBe(false)
    expect(sameProgram(null, '/a/b/ollama', 'darwin')).toBe(false)
  })
})

describe('pidsRunningUnder and sweepPrograms', () => {
  it('asks PowerShell for the programs running from the folder, and never lists the app itself', () => {
    const { run, calls } = fakeRunner(`4100\r\n${process.pid}\r\n\r\n4200\r\nnot a number\r\n`)
    expect(pidsRunningUnder('C:\\PostCall\\resources', 'win32', run)).toEqual([4100, 4200])
    expect(calls[0]?.file).toBe('powershell.exe')
    expect(calls[0]?.args.join(' ')).toContain('Win32_Process')
  })

  it('only looks at programs inside the folder, so a system Ollama is never touched', () => {
    const seen: Array<NodeJS.ProcessEnv | undefined> = []
    const run: Runner = (_file, _args, env) => {
      seen.push(env)
      return ''
    }
    pidsRunningUnder('C:\\PostCall\\resources', 'win32', run)
    expect(seen[0]?.POSTCALL_PROGRAMS_DIR).toBe('C:\\PostCall\\resources\\')
  })

  it('does nothing outside Windows, where process groups cover this', () => {
    const { run, calls } = fakeRunner('1\n')
    expect(pidsRunningUnder('/opt/x', 'linux', run)).toEqual([])
    expect(calls).toEqual([])
  })

  it('returns an empty list when PowerShell fails', () => {
    const failing: Runner = () => {
      throw new Error('powershell is not available')
    }
    expect(pidsRunningUnder('C:\\x', 'win32', failing)).toEqual([])
  })

  it('ends each program it finds', () => {
    const calls: string[][] = []
    const run: Runner = (file, args) => {
      calls.push([file, ...args])
      return file === 'powershell.exe' ? '11\n22\n' : ''
    }
    expect(sweepPrograms('C:\\PostCall\\resources', 'win32', run)).toBe(2)
    expect(calls.filter(c => c[0] === 'taskkill').map(c => c[2])).toEqual(['11', '22'])
  })
})

describe('reapOrphans on Windows', () => {
  it('stops a leftover program recorded in the pid file when the image name matches', async () => {
    const file = path.join(tempDir(), 'services.json')
    recordService(file, 'ollama', 5555, 'C:\\PostCall\\resources\\ollama\\ollama.exe')
    recordService(file, 'api', 6666, 'C:\\PostCall\\resources\\api\\postcall-api.exe')
    // 5555 is still our ollama.exe; 6666 now belongs to some other program (a recycled pid)
    const lookup = (pid: number): string | null => (pid === 5555 ? 'ollama.exe' : 'notepad.exe')
    expect(await reapOrphans(file, lookup, 10, 'win32')).toEqual(['ollama'])
    expect(fs.existsSync(file)).toBe(false)
  })
})
