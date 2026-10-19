import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { packagedResources, root } from './lib.mjs'
import { preflight, report } from './preflight.mjs'
import { selectSteps, STEPS } from './steps.mjs'

const workflow = fs.readFileSync(path.join(root, '.github', 'workflows', 'build.yml'), 'utf8')

test('npm run dist runs the same scripts as CI, in the same order', () => {
  const inCi = [...workflow.matchAll(/^\s+run: node scripts\/([\w.-]+\.mjs)/gm)].map(m => m[1])
  assert.deepEqual(STEPS.map(step => step.script), inCi)
})

test('the packaged-program smoke test looks where CI looks, on every system', () => {
  for (const [name, id] of [['macos-arm64', 'darwin-arm64'], ['windows-x64', 'win32-x64'], ['linux-x64', 'linux-x64']]) {
    const block = new RegExp(`name: ${name}\\n\\s+runner: [\\w.-]+\\n\\s+resources: (\\S+)`).exec(workflow)
    assert.equal(block?.[1], packagedResources(id), name)
  }
  assert.match(workflow, /node scripts\/smoke\.mjs --resources "\$\{\{ matrix\.resources \}\}"/)
})

test('the root package exposes the command and needs no dependencies', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
  assert.equal(pkg.scripts.dist, 'node scripts/dist.mjs')
  assert.equal(pkg.dependencies, undefined)
  assert.equal(pkg.devDependencies, undefined)
})

test('steps can be resumed, picked or filtered, and a wrong name explains itself', () => {
  assert.deepEqual(selectSteps({}).map(s => s.id), STEPS.map(s => s.id))
  assert.deepEqual(selectSteps({ from: 'package' }).map(s => s.id), ['package', 'smoke-packaged', 'installer-sizes'])
  assert.deepEqual(selectSteps({ only: 'build-api' }).map(s => s.id), ['build-api'])
  assert.deepEqual(selectSteps({ skipSmoke: true }).map(s => s.id).filter(id => id.startsWith('smoke')), [])
  assert.throws(() => selectSteps({ from: 'nope' }), /--from nope: no such step. The steps are: fetch-ollama/)
  assert.throws(() => selectSteps({ from: 'package', only: 'package' }), /not both/)
})

/** A computer that has everything, which a test then takes things away from. */
function computer(overrides = {}) {
  const have = new Set(['git', 'uv', 'cmake', 'gcc', 'g++', 'make', 'nasm', 'zstd', 'ar'])
  const files = new Set([
    'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\vswhere.exe',
    'C:\\msys64\\usr\\bin\\bash.exe',
    'C:\\msys64\\ucrt64\\bin\\gcc.exe',
    'C:\\msys64\\ucrt64\\bin\\nasm.exe',
    'C:\\msys64\\usr\\bin\\make.exe',
    'C:\\Windows\\System32\\tar.exe',
  ])
  return { node: () => '24.13.0', has: c => have.has(c), exists: f => files.has(f), freeBytes: () => 50e9, succeeds: () => true, env: {}, have, files, ...overrides }
}
const failed = checks => checks.filter(c => !c.ok).map(c => c.name.split(' (')[0])

test('a computer with everything passes on each system', () => {
  for (const id of ['darwin-arm64', 'linux-x64', 'win32-x64']) assert.deepEqual(failed(preflight(id, computer())), [], id)
})

test('what is missing is named with how to get it', () => {
  const old = computer({ node: () => '20.11.0', freeBytes: () => 3e9 })
  old.have.delete('uv')
  const names = failed(preflight('linux-x64', old))
  assert.ok(names.some(n => n.startsWith('Node 22')) && names.includes('uv') && names.some(n => n.includes('12 GB')))
  old.have.delete('nasm')
  const lines = []
  assert.equal(report(preflight('linux-x64', old), l => lines.push(l)), false)
  assert.ok(lines.join('\n').includes('sudo apt install build-essential cmake nasm zstd binutils'))
})

test('Windows needs the compiler, MSYS2 with its tools, and the system tar', () => {
  const win = computer({ succeeds: () => false })
  win.files.delete('C:\\msys64\\ucrt64\\bin\\nasm.exe')
  const names = failed(preflight('win32-x64', win))
  assert.ok(names.some(n => n.startsWith('Visual Studio 2022')))
  assert.ok(names.some(n => n.startsWith('MSYS2')))
  assert.ok(!names.some(n => n.startsWith('Windows')), 'tar.exe is present')
  const lines = []
  report(preflight('win32-x64', win), l => lines.push(l))
  assert.ok(lines.join('\n').includes('mingw-w64-ucrt-x86_64-gcc'))
})

test('MSYS2_ROOT moves where Windows looks for MSYS2', () => {
  const win = computer({ env: { MSYS2_ROOT: 'D:\\tools\\msys64' } })
  assert.ok(failed(preflight('win32-x64', win)).some(n => n.startsWith('MSYS2 at D:\\tools\\msys64')))
})

test('macOS needs the command line tools and cmake', () => {
  const mac = computer({ succeeds: () => false })
  mac.have.delete('cmake')
  assert.deepEqual(failed(preflight('darwin-arm64', mac)).sort(), ['Xcode command line tools', 'cmake'])
})
