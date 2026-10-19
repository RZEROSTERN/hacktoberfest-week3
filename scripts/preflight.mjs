// Checks that this computer has what building the installer needs, and says how to get what is missing, before a
// long build starts. Everything it asks of the system goes through `probes`, so each system's list is tested from any host.
import fs from 'node:fs'
import path from 'node:path'
import { capture, root, which } from './lib.mjs'

const MIN_NODE_MAJOR = 22
const MIN_FREE_BYTES = 12e9 // downloads (up to 1.4 GB), compiler output, PyInstaller, electron-builder, the installers

/** What the real computer answers. */
export const realProbes = {
  node: () => process.versions.node,
  has: command => which(command) !== null,
  exists: file => fs.existsSync(file),
  freeBytes: dir => {
    const stat = fs.statfsSync(dir)
    return stat.bavail * stat.bsize
  },
  succeeds: (command, args) => capture(command, args).status === 0,
  env: process.env,
}

const WINDOWS_PACKAGES = 'pacman -S --needed make diffutils xz curl mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-nasm'

/** The list of checks for one system. Each is { name, ok, hint }. */
export function preflight(id, probes = realProbes, repo = root) {
  const checks = []
  const check = (name, ok, hint) => checks.push({ name, ok: Boolean(ok), hint })

  const major = Number.parseInt(probes.node().split('.')[0], 10)
  check(`Node ${MIN_NODE_MAJOR} or newer (this is ${probes.node()})`, major >= MIN_NODE_MAJOR, 'install Node 24 from https://nodejs.org')
  check('git', probes.has('git'), 'install git from https://git-scm.com')
  check('uv (runs Python 3.12 and the api build)', probes.has('uv'), 'install uv: https://docs.astral.sh/uv/getting-started/installation/')
  const free = probes.freeBytes(repo)
  check(`12 GB of free disk (${(free / 1e9).toFixed(1)} GB here)`, free >= MIN_FREE_BYTES, 'free some space: downloads and build files need about 12 GB')

  if (id === 'darwin-arm64') {
    check('Xcode command line tools (compiler for whisper.cpp)', probes.succeeds('xcode-select', ['-p']), 'run: xcode-select --install')
    check('cmake', probes.has('cmake') || probes.exists(path.join(repo, 'spike', '.venv', 'bin', 'cmake')), 'run: brew install cmake')
  } else if (id === 'linux-x64') {
    for (const tool of ['gcc', 'g++', 'make', 'cmake', 'nasm', 'zstd', 'ar']) {
      check(tool, probes.has(tool), 'run: sudo apt install build-essential cmake nasm zstd binutils')
    }
  } else {
    const programFiles = probes.env['ProgramFiles(x86)'] ?? 'C:\\Program Files (x86)'
    const vswhere = path.win32.join(programFiles, 'Microsoft Visual Studio', 'Installer', 'vswhere.exe')
    check('cmake', probes.has('cmake'), 'install CMake from https://cmake.org/download/ (add it to the PATH)')
    check(
      'Visual Studio 2022 with "Desktop development with C++" (compiler for whisper.cpp)',
      probes.exists(vswhere) &&
        probes.succeeds(vswhere, ['-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath']),
      'install Visual Studio Build Tools 2022 from https://visualstudio.microsoft.com/downloads/ and tick "Desktop development with C++"',
    )
    const msys = probes.env.MSYS2_ROOT || 'C:\\msys64'
    check(`MSYS2 at ${msys} with the FFmpeg tools`, ['usr\\bin\\bash.exe', 'ucrt64\\bin\\gcc.exe', 'ucrt64\\bin\\nasm.exe', 'usr\\bin\\make.exe'].every(f => probes.exists(path.win32.join(msys, f))), `install MSYS2 from https://www.msys2.org/, open its "MSYS2 UCRT64" shell and run: ${WINDOWS_PACKAGES}`)
    check("Windows' own tar.exe (Windows 10 or later)", probes.exists(path.win32.join(probes.env.SystemRoot ?? 'C:\\Windows', 'System32', 'tar.exe')), 'update Windows: tar.exe ships with Windows 10 and 11')
  }
  return checks
}

/** Prints the checks. Returns true when everything is in place. */
export function report(checks, log = console.log) {
  for (const c of checks) log(`${c.ok ? 'ok     ' : 'MISSING'}  ${c.name}`)
  const missing = checks.filter(c => !c.ok)
  if (missing.length > 0) {
    log('\nWhat to do:')
    for (const c of missing) log(`  - ${c.name.split(' (')[0]}: ${c.hint}`)
  }
  return missing.length === 0
}
