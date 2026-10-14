import type { DataDirs, Layout } from './layout'

/** Only these variables are passed on, so a user's own OLLAMA_* or SCOPEWISE_* settings cannot leak in. */
const PASS_THROUGH = ['PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'USER', 'LOGNAME']

function base(source: NodeJS.ProcessEnv): Record<string, string> {
  const env: Record<string, string> = {}
  for (const key of PASS_THROUGH) {
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
export const APP_HOST = 'scopewise'
export const APP_ORIGIN = `${APP_SCHEME}://${APP_HOST}`

export function ollamaUrl(ports: Ports): string {
  return `http://127.0.0.1:${ports.ollama}`
}

export function apiUrl(ports: Ports): string {
  return `http://127.0.0.1:${ports.api}`
}

/** The bundled Ollama: loopback only, its own home and models folder, no cloud models. */
export function ollamaEnv(ports: Ports, dirs: DataDirs, source: NodeJS.ProcessEnv): Record<string, string> {
  return {
    ...base(source),
    HOME: dirs.ollamaHome,
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
): Record<string, string> {
  return {
    ...base(source),
    SCOPEWISE_HOST: '127.0.0.1',
    SCOPEWISE_PORT: String(ports.api),
    SCOPEWISE_OLLAMA_URL: ollamaUrl(ports),
    SCOPEWISE_DATA_DIR: dirs.data,
    SCOPEWISE_MODELS_DIR: dirs.models,
    SCOPEWISE_CORS_ORIGINS: JSON.stringify([APP_ORIGIN]),
    SCOPEWISE_WHISPER_CLI: layout.whisperBinary,
    SCOPEWISE_PARENT_PID: String(parentPid),
  }
}
