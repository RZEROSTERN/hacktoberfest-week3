import type { DataDirs, Layout } from './layout'

/** Only these variables are passed on, so a user's own OLLAMA_* or POSTCALL_* settings cannot leak in. */
const PASS_THROUGH = ['PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'USER', 'LOGNAME']

/**
 * What Windows programs need to start at all: the system folder (sockets and DLL loading fail without
 * SystemRoot), the temporary folder (the api unpacks itself there), the program search extensions and
 * the processor facts the engines read. Nothing here carries a user's own settings.
 */
const WINDOWS_PASS_THROUGH = [
  'SystemRoot',
  'SystemDrive',
  'windir',
  'TEMP',
  'TMP',
  'PATHEXT',
  'COMSPEC',
  'ProgramData',
  'NUMBER_OF_PROCESSORS',
  'PROCESSOR_ARCHITECTURE',
  'USERNAME',
]

function base(source: NodeJS.ProcessEnv, platform: NodeJS.Platform): Record<string, string> {
  const env: Record<string, string> = {}
  for (const key of platform === 'win32' ? [...PASS_THROUGH, ...WINDOWS_PASS_THROUGH] : PASS_THROUGH) {
    const value = source[key]
    if (value !== undefined) env[key] = value
  }
  return env
}

export interface Ports {
  ollama: number
  api: number
}

export const APP_SCHEME = 'app'
export const APP_HOST = 'postcall'
export const APP_ORIGIN = `${APP_SCHEME}://${APP_HOST}`

export function ollamaUrl(ports: Ports): string {
  return `http://127.0.0.1:${ports.ollama}`
}

export function apiUrl(ports: Ports): string {
  return `http://127.0.0.1:${ports.api}`
}

/** The bundled Ollama: loopback only, its own home and models folder, no cloud models. */
export function ollamaEnv(
  ports: Ports,
  dirs: DataDirs,
  source: NodeJS.ProcessEnv,
  platform: NodeJS.Platform = process.platform,
): Record<string, string> {
  return {
    ...base(source, platform),
    HOME: dirs.ollamaHome,
    // Ollama finds its home through USERPROFILE on Windows, so it needs the same redirect as HOME.
    ...(platform === 'win32' ? { USERPROFILE: dirs.ollamaHome } : {}),
    OLLAMA_HOST: `127.0.0.1:${ports.ollama}`,
    OLLAMA_MODELS: dirs.ollamaModels,
    OLLAMA_NO_CLOUD: '1',
  }
}

export function apiEnv(
  ports: Ports,
  dirs: DataDirs,
  layout: Layout,
  parentPid: number,
  source: NodeJS.ProcessEnv,
  platform: NodeJS.Platform = process.platform,
): Record<string, string> {
  return {
    ...base(source, platform),
    POSTCALL_HOST: '127.0.0.1',
    POSTCALL_PORT: String(ports.api),
    POSTCALL_OLLAMA_URL: ollamaUrl(ports),
    POSTCALL_DATA_DIR: dirs.data,
    POSTCALL_MODELS_DIR: dirs.models,
    POSTCALL_CORS_ORIGINS: JSON.stringify([APP_ORIGIN]),
    POSTCALL_WHISPER_CLI: layout.whisperBinary,
    ...(layout.ffmpegBinary ? { POSTCALL_FFMPEG: layout.ffmpegBinary } : {}),
    POSTCALL_PARENT_PID: String(parentPid),
  }
}
