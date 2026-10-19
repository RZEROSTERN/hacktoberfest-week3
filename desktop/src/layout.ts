import nodePath from 'node:path'

/** Where everything the shell starts lives. The packaged app and `npm start` use different roots. */
export interface Layout {
  /** The folder the bundled programs sit in: the app's resources, or desktop/build when unpackaged. */
  programsDir: string
  ollamaBinary: string
  apiBinary: string
  whisperBinary: string
  /** The audio converter the api is told to use. macOS has its own, so there is none to bundle there. */
  ffmpegBinary: string | null
  webRoot: string
  noticesFile: string
}

/** Where each bundled program is, inside its folder, on one system. */
export function programNames(platform: NodeJS.Platform): { ollama: string[]; api: string; whisper: string; ffmpeg: string[] | null } {
  const exe = platform === 'win32' ? '.exe' : ''
  return {
    // Ollama's Linux archive is `bin/ollama` plus `lib/ollama/`, and it finds its libraries relative to the
    // program, so that layout stays as it came. Its macOS and Windows archives are flat.
    ollama: platform === 'linux' ? ['ollama', 'bin', 'ollama'] : ['ollama', `ollama${exe}`],
    api: `postcall-api${exe}`,
    whisper: `whisper-cli${exe}`,
    ffmpeg: platform === 'darwin' ? null : ['ffmpeg', `ffmpeg${exe}`],
  }
}

export function resolveLayout(opts: {
  packaged: boolean
  resourcesPath: string
  appRoot: string
  platform?: NodeJS.Platform
}): Layout {
  const platform = opts.platform ?? process.platform
  const names = programNames(platform)
  // The path rules of the system the layout is for, so the result is the same wherever it is computed.
  const path = platform === 'win32' ? nodePath.win32 : nodePath.posix
  // Packaged: everything is in extraResources, next to the asar and never inside it, so it can be run.
  // Unpackaged: the files the build scripts leave in desktop/build, and the generated web app.
  const dir = opts.packaged ? opts.resourcesPath : path.join(opts.appRoot, 'build')
  return {
    programsDir: dir,
    ollamaBinary: path.join(dir, ...names.ollama),
    apiBinary: path.join(dir, 'api', names.api),
    whisperBinary: path.join(dir, 'whisper', names.whisper),
    ffmpegBinary: names.ffmpeg && path.join(dir, ...names.ffmpeg),
    webRoot: opts.packaged ? path.join(dir, 'web') : path.join(opts.appRoot, '..', 'web', '.output', 'public'),
    noticesFile: opts.packaged ? path.join(dir, 'THIRD_PARTY_NOTICES.md') : path.join(opts.appRoot, '..', 'THIRD_PARTY_NOTICES.md'),
  }
}

/** Folders the app owns inside its user data folder. Nothing is written anywhere else. */
export interface DataDirs {
  data: string
  models: string
  ollamaModels: string
  ollamaHome: string
  logs: string
  pidFile: string
}

export function dataDirs(userData: string): DataDirs {
  return {
    data: nodePath.join(userData, 'data'),
    models: nodePath.join(userData, 'models'),
    ollamaModels: nodePath.join(userData, 'models', 'ollama'),
    ollamaHome: nodePath.join(userData, 'ollama-home'),
    logs: nodePath.join(userData, 'logs'),
    pidFile: nodePath.join(userData, 'services.json'),
  }
}
