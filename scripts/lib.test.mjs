import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { formatBytes, platformId, programPaths, sha256File, sizeOf, stampMatches, versions, writeStamp } from './lib.mjs'

test('only the three build systems are accepted', () => {
  assert.equal(platformId('darwin', 'arm64'), 'darwin-arm64')
  assert.equal(platformId('win32', 'x64'), 'win32-x64')
  assert.equal(platformId('linux', 'x64'), 'linux-x64')
  for (const [p, a] of [['darwin', 'x64'], ['linux', 'arm64'], ['win32', 'arm64'], ['freebsd', 'x64']]) {
    assert.throws(() => platformId(p, a), /not a supported build system/)
  }
})

test('programs sit where the desktop shell looks for them', () => {
  assert.deepEqual(programPaths('darwin-arm64').ollama, ['ollama', 'ollama'])
  assert.equal(programPaths('darwin-arm64').ffmpeg, null)
  assert.deepEqual(programPaths('linux-x64').ollama, ['ollama', 'bin', 'ollama'])
  assert.deepEqual(programPaths('linux-x64').ffmpeg, ['ffmpeg', 'ffmpeg'])
  assert.deepEqual(programPaths('win32-x64').ollama, ['ollama', 'ollama.exe'])
  assert.deepEqual(programPaths('win32-x64').api, ['api', 'postcall-api.exe'])
  assert.deepEqual(programPaths('win32-x64').whisper, ['whisper', 'whisper-cli.exe'])
})

test('every bundled download is pinned by a checksum', () => {
  const hex = /^[0-9a-f]{64}$/
  assert.match(versions.ollama.licenseSha256, hex)
  for (const [id, asset] of Object.entries(versions.ollama.assets)) assert.match(asset.sha256, hex, id)
  assert.match(versions.ffmpeg.sha256, hex)
  assert.match(versions.smokeModel.sha256, hex)
  assert.match(versions.whisper.rev, /^[0-9a-f]{40}$/)
  assert.deepEqual(Object.keys(versions.ollama.assets).sort(), ['darwin-arm64', 'linux-x64', 'win32-x64'])
})

test('sizes are shown in plain units', () => {
  assert.equal(formatBytes(1_500_000_000), '1.50 GB')
  assert.equal(formatBytes(306_493_098), '306.5 MB')
  assert.equal(formatBytes(512), '512 B')
})

test('a checksum, a folder size and a build stamp', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pc-lib-'))
  const file = path.join(dir, 'a.bin')
  fs.writeFileSync(file, 'hello')
  assert.equal(sha256File(file), crypto.createHash('sha256').update('hello').digest('hex'))
  fs.mkdirSync(path.join(dir, 'sub'))
  fs.writeFileSync(path.join(dir, 'sub', 'b.bin'), '12345')
  assert.equal(sizeOf(dir), 10)
  assert.equal(stampMatches(dir, { rev: 1 }), false)
  writeStamp(dir, { rev: 1 })
  assert.equal(stampMatches(dir, { rev: 1 }), true)
  assert.equal(stampMatches(dir, { rev: 2 }), false)
})
