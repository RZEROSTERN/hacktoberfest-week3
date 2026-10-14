import path from 'node:path'

/** Where everything the shell starts lives. The packaged app and `npm start` use different roots. */
export interface Layout {
  ollamaBinary: string
  apiBinary: string
  whisperBinary: string
  /** The audio converter the api is told to use. macOS has its own, so there is none to bundle there. */
  ffmpegBinary: string | null
  webRoot: string
  noticesFile: string
}

export function resolveLayout(opts: {
  packaged: boolean
  resourcesPath: string
  appRoot: string
  platform?: NodeJS.Platform
}): Layout {
  const linux = (opts.platform ?? process.platform) === 'linux'
  // Ollama's Linux archive is `bin/ollama` plus `lib/ollama/`, and it finds its libraries relative to
  // the program, so that layout stays as it came. The macOS archive is flat.
  const ollama = linux ? path.join('ollama', 'bin', 'ollama') : path.join('ollama', 'ollama')
  const ffmpeg = linux ? path.join('ffmpeg', 'ffmpeg') : null
  if (opts.packaged) {
    const r = opts.resourcesPath
    return {
      ollamaBinary: path.join(r, ollama),
      apiBinary: path.join(r, 'api', 'postcall-api'),
      whisperBinary: path.join(r, 'whisper', 'whisper-cli'),
      ffmpegBinary: ffmpeg && path.join(r, ffmpeg),
      webRoot: path.join(r, 'web'),
      noticesFile: path.join(r, 'THIRD_PARTY_NOTICES.md'),
    }
  }
  // Unpackaged: the files the build scripts leave in desktop/build, and the generated web app.
  const build = path.join(opts.appRoot, 'build')
  return {
    ollamaBinary: path.join(build, ollama),
    apiBinary: path.join(build, 'api', 'postcall-api'),
    whisperBinary: path.join(build, 'whisper', 'whisper-cli'),
    ffmpegBinary: ffmpeg && path.join(build, ffmpeg),
    webRoot: path.join(opts.appRoot, '..', 'web', '.output', 'public'),
    noticesFile: path.join(opts.appRoot, '..', 'THIRD_PARTY_NOTICES.md'),
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
    data: path.join(userData, 'data'),
    models: path.join(userData, 'models'),
    ollamaModels: path.join(userData, 'models', 'ollama'),
    ollamaHome: path.join(userData, 'ollama-home'),
    logs: path.join(userData, 'logs'),
    pidFile: path.join(userData, 'services.json'),
  }
}
