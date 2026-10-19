// Builds one self-contained whisper-cli from the pinned whisper.cpp revision into desktop/build/whisper/.
//   macOS    Metal, shaders embedded, no CPU tuning (runs on every Apple Silicon chip).
//   Linux    CPU only, AVX2 + FMA + F16C (any x86-64 CPU since Intel Haswell 2013 / AMD Excavator 2015),
//            libstdc++ linked statically.
//   Windows  CPU only, same instruction sets, static MSVC runtime (no Visual C++ Redistributable needed), no
//            OpenMP (it needs a separate DLL), and a UTF-8 application manifest so accented user names work.
// The pinned revision is the one the model benchmarks and tests used.
import fs from 'node:fs'
import path from 'node:path'
import { buildDir, capture, endGroup, group, mkdirp, platformId, rmrf, root, run, stampMatches, versions, which, writeStamp } from './lib.mjs'

const id = platformId()
const { repo, rev } = versions.whisper
const src = path.join(root, '.dev', 'whisper.cpp')
const out = path.join(buildDir, 'whisper')
const exe = id.startsWith('win32') ? '.exe' : ''
const inputs = { rev, id, script: fs.readFileSync(new URL(import.meta.url), 'utf8') }

group(`whisper-cli ${rev.slice(0, 7)} for ${id}`)
if (stampMatches(out, inputs) && fs.existsSync(path.join(out, `whisper-cli${exe}`))) {
  console.log('whisper-cli is already built from these inputs')
  endGroup()
  process.exit(0)
}

// A shallow checkout of exactly the pinned revision.
if (!fs.existsSync(path.join(src, '.git'))) {
  mkdirp(src)
  run('git', ['init', '-q', src])
  run('git', ['-C', src, 'remote', 'add', 'origin', repo])
}
const head = capture('git', ['-C', src, 'rev-parse', 'HEAD']).stdout.trim()
if (head !== rev) {
  run('git', ['-C', src, 'fetch', '-q', '--depth', '1', 'origin', rev])
  run('git', ['-C', src, 'checkout', '-q', 'FETCH_HEAD'])
}

// `make whisper-dev` installs cmake into spike/.venv on a Mac that has none on its PATH.
const cmake = which('cmake') ?? path.join(root, 'spike', '.venv', 'bin', 'cmake')
const common = ['-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF', '-DWHISPER_BUILD_TESTS=OFF', '-DWHISPER_BUILD_SERVER=OFF']
const x86 = ['-DGGML_NATIVE=OFF', '-DGGML_OPENMP=OFF', '-DGGML_AVX=ON', '-DGGML_AVX2=ON', '-DGGML_FMA=ON', '-DGGML_F16C=ON']
const build = path.join(src, 'build-static')
let flags
if (id === 'darwin-arm64') {
  flags = [...common, '-DGGML_NATIVE=OFF', '-DGGML_METAL=ON', '-DGGML_METAL_EMBED_LIBRARY=ON', '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0']
} else if (id === 'linux-x64') {
  flags = [...common, ...x86, '-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc']
} else {
  const manifest = path.join(root, 'scripts', 'windows-utf8.manifest')
  flags = [
    ...common,
    ...x86,
    '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
    `-DCMAKE_EXE_LINKER_FLAGS=/MANIFEST:EMBED /MANIFESTINPUT:${manifest}`,
    '-A',
    'x64',
  ]
}
run(cmake, ['-S', src, '-B', build, ...flags])
run(cmake, ['--build', build, '--config', 'Release', '--target', 'whisper-cli', '-j'])

// Visual Studio puts the program in a Release folder; the other generators do not.
const built = [path.join(build, 'bin', 'Release', `whisper-cli${exe}`), path.join(build, 'bin', `whisper-cli${exe}`)].find(fs.existsSync)
if (!built) throw new Error('whisper-cli was not produced')
rmrf(out)
mkdirp(out)
fs.copyFileSync(built, path.join(out, `whisper-cli${exe}`))
fs.copyFileSync(path.join(src, 'LICENSE'), path.join(out, 'LICENSE'))
if (process.platform !== 'win32') fs.chmodSync(path.join(out, 'whisper-cli'), 0o755)
writeStamp(out, inputs)
console.log(`built ${path.relative(process.cwd(), path.join(out, `whisper-cli${exe}`))} (${(fs.statSync(path.join(out, `whisper-cli${exe}`)).size / 1e6).toFixed(1)} MB)`)
endGroup()
