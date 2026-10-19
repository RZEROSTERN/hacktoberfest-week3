// Builds the minimal LGPL FFmpeg (see build-ffmpeg.sh) into desktop/build/ffmpeg/ on Windows and Linux.
// macOS does not bundle one. On Windows the recipe runs in MSYS2's UCRT64 shell; CI installs it with
// msys2/setup-msys2, and on a developer machine it must be installed with these packages:
//   pacman -S --needed make diffutils xz curl mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-nasm
import fs from 'node:fs'
import path from 'node:path'
import { buildDir, endGroup, group, platformId, root, run, stampMatches, versions, writeStamp } from './lib.mjs'

const id = platformId()
if (id === 'darwin-arm64') {
  console.log('macOS uses its own audio converter (afconvert): no FFmpeg to build')
  process.exit(0)
}

const out = path.join(buildDir, 'ffmpeg')
const exe = id === 'win32-x64' ? '.exe' : ''
const recipe = path.join(root, 'scripts', 'build-ffmpeg.sh')
const inputs = { ...versions.ffmpeg, id, recipe: fs.readFileSync(recipe, 'utf8') }

group(`FFmpeg ${versions.ffmpeg.version} for ${id}`)
if (stampMatches(out, inputs) && fs.existsSync(path.join(out, `ffmpeg${exe}`))) {
  console.log('FFmpeg is already built from these inputs')
  endGroup()
  process.exit(0)
}

const env = {
  ...process.env,
  FFMPEG_VERSION: versions.ffmpeg.version,
  FFMPEG_URL: versions.ffmpeg.url,
  FFMPEG_SHA256: versions.ffmpeg.sha256,
}
fs.rmSync(out, { recursive: true, force: true })
const fixtures = path.join(root, 'api', 'tests', 'data')
if (id === 'win32-x64') {
  const msys = process.env.MSYS2_ROOT ?? 'C:\\msys64'
  const bash = path.join(msys, 'usr', 'bin', 'bash.exe')
  if (!fs.existsSync(bash)) throw new Error(`MSYS2 was not found at ${msys}. Install it from https://www.msys2.org/ (or set MSYS2_ROOT).`)
  // MSYS2 wants /c/... paths; `cygpath -u` converts them inside its own shell.
  // The compiler is in /ucrt64/bin. The login profile is not relied on to put it on the PATH: that was missing in CI.
  const script = `export PATH=/ucrt64/bin:/usr/bin:$PATH && cd "$(cygpath -u '${root}')" && FIXTURES="$(cygpath -u '${fixtures}')" ./scripts/build-ffmpeg.sh "$(cygpath -u '${out}')"`
  run(bash, ['-lc', script], { env: { ...env, MSYSTEM: 'UCRT64', CHERE_INVOKING: '1' } })
} else {
  run(recipe, [out], { env: { ...env, FIXTURES: fixtures } })
}
writeStamp(out, inputs)
endGroup()
