import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { checkTag, checksumLines, findInstallers, prepare, renderNotes } from './release.mjs'

test('a tag must be a version and match the versions the installers carry', () => {
  assert.deepEqual(checkTag('v1.2.3', '1.2.3', '1.2.3'), [])
  assert.deepEqual(checkTag('v1.2.3-rc.1', '1.2.3-rc.1', '1.2.3-rc.1'), [])
  assert.match(checkTag('1.2.3', '1.2.3', '1.2.3')[0], /not a version tag/)
  assert.match(checkTag('v1.2', '1.2.0', '1.2.0')[0], /not a version tag/)
  assert.match(checkTag('release-1', '1', '1')[0], /not a version tag/)
  assert.equal(checkTag('v2.0.0', '1.0.0', '2.0.0').length, 1)
  assert.match(checkTag('v2.0.0', '1.0.0', '2.0.0')[0], /desktop\/package\.json/)
  assert.match(checkTag('v2.0.0', '2.0.0', '1.0.0')[0], /api\/pyproject\.toml/)
  assert.equal(checkTag('v2.0.0', '1.0.0', '1.0.0').length, 2)
})

const FILES = ['PostCall-1.0.0-arm64.dmg', 'PostCall-1.0.0-x64-setup.exe', 'PostCall-1.0.0-x86_64.AppImage', 'postcall_1.0.0_amd64.deb']

test('all four installers must be there, and the per-file checksums are ignored', () => {
  const withSums = [...FILES, ...FILES.map(f => `${f}.sha256`), 'something-else.txt']
  assert.deepEqual(findInstallers(withSums).map(k => k.file), FILES)
  assert.throws(() => findInstallers(FILES.slice(0, 3)), /missing for: Linux Mint, Ubuntu and Debian/)
  assert.throws(() => findInstallers([]), /missing for: macOS/)
})

test('the checksum list is sorted and readable by sha256sum', () => {
  assert.equal(checksumLines([{ file: 'b.exe', sha: 'bb' }, { file: 'a.dmg', sha: 'aa' }]), 'aa  a.dmg\nbb  b.exe\n')
})

test('the notes name every file, its size and how to open the unsigned app', () => {
  const rows = FILES.map((file, i) => ({ file, system: findInstallers(FILES)[i].system, bytes: 200_000_000 + i }))
  const notes = renderNotes({ version: '1.0.0', rows })
  for (const f of FILES) assert.ok(notes.includes(f), f)
  assert.ok(notes.includes('Open Anyway') && notes.includes('Run anyway') && notes.includes('chmod +x'))
  assert.ok(notes.includes('SHA256SUMS') && notes.includes('not signed'))
})

test('preparing a folder writes the checksums and the notes and lists what to attach', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pc-release-'))
  for (const f of FILES) fs.writeFileSync(path.join(dir, f), f)
  fs.writeFileSync(path.join(dir, 'PostCall-1.0.0-arm64.dmg.sha256'), 'ignored')
  const attach = prepare(dir, '1.0.0')
  assert.deepEqual(attach, [...FILES, 'SHA256SUMS'])
  const sums = fs.readFileSync(path.join(dir, 'SHA256SUMS'), 'utf8').trim().split('\n')
  assert.equal(sums.length, 4)
  assert.ok(sums.every(line => /^[0-9a-f]{64}  \S+$/.test(line)))
  assert.ok(fs.readFileSync(path.join(dir, 'RELEASE_NOTES.md'), 'utf8').startsWith('# PostCall 1.0.0'))
})
