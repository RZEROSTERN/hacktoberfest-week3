import fs from 'node:fs'
import path from 'node:path'
import { app, BrowserWindow, dialog, Menu, protocol, session, shell } from 'electron'
import { apiEnv, apiUrl, APP_ORIGIN, ollamaEnv, ollamaUrl, type Ports } from './env'
import { dataDirs, resolveLayout, type DataDirs, type Layout } from './layout'
import { resolveLocale, say, type Locale } from './locale'
import { reapOrphans } from './pidfile'
import { twoFreePorts } from './ports'
import { serve } from './protocol'
import { startPage } from './startPage'
import { isAllowedExternal, isAllowedRequest, isAppUrl } from './security'
import { Service, Supervisor } from './supervisor'

// The web app is served from its own scheme so it behaves like a normal site (absolute asset paths,
// CORS with an explicit origin) without ever opening a port or loading file:// pages.
protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true } },
])

// The packaged app's data lives in "PostCall"; running from the repository uses its own folder, so a
// development shell never shares data, models or the single-instance lock with an installed app.
if (!app.isPackaged) app.setPath('userData', path.join(app.getPath('appData'), 'PostCall (development)'))

const OLLAMA_START_TIMEOUT_MS = 60_000
const API_START_TIMEOUT_MS = 90_000 // the packaged api unpacks itself on a cold start

const supervisor = new Supervisor()
let mainWindow: BrowserWindow | null = null
let quitting = false
let reportedFatal = false

// The language of the system, for what is shown before the web app (which has its own picker) is loaded.
// `app.getLocale()` is only valid once the app is ready; before that it is English.
const systemLocale = (): Locale => (app.isReady() ? resolveLocale(app.getLocale()) : 'en')

function showFatal(title: string, detail: string, logs: string): void {
  if (reportedFatal) return
  reportedFatal = true
  void dialog
    .showMessageBox({
      type: 'error',
      title: 'PostCall',
      message: title,
      detail: `${detail}\n\n${say(systemLocale(), 'dialog.advice')}`,
      buttons: [say(systemLocale(), 'dialog.quit'), say(systemLocale(), 'dialog.showLogs')],
      defaultId: 0,
    })
    .then(({ response }) => {
      if (response === 1) void shell.openPath(logs)
      app.quit()
    })
}

function createWindow(apiBase: string): BrowserWindow {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    title: 'PostCall',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      devTools: !app.isPackaged,
      additionalArguments: [`--postcall-api-base=${apiBase}`],
    },
  })
  win.once('ready-to-show', () => win.show())
  win.on('closed', () => {
    mainWindow = null
  })

  const contents = win.webContents
  // Links that open a new window go to the user's browser, but only the few that are allowed.
  contents.setWindowOpenHandler(({ url }) => {
    if (isAllowedExternal(url)) void shell.openExternal(url)
    return { action: 'deny' }
  })
  contents.on('will-navigate', (event, url) => {
    if (isAppUrl(url)) return
    event.preventDefault()
    if (isAllowedExternal(url)) void shell.openExternal(url)
  })
  contents.on('will-attach-webview', event => event.preventDefault())
  return win
}

function lockDownSession(apiOrigin: string): void {
  const ses = session.defaultSession
  ses.setPermissionRequestHandler((_contents, _permission, callback) => callback(false))
  ses.setPermissionCheckHandler(() => false)
  ses.webRequest.onBeforeRequest((details, callback) => {
    callback({ cancel: !isAllowedRequest(details.url, apiOrigin) })
  })
  protocol.handle('app', (request) => {
    const served = serve(webRoot, request.url, apiOrigin)
    return new Response(served.body, { status: served.status, headers: served.headers })
  })
}

function buildMenu(): void {
  const template: Electron.MenuItemConstructorOptions[] = [
    { role: 'appMenu' },
    { role: 'editMenu' }, // without it copy and paste do not work in text fields on macOS
    ...(app.isPackaged ? [] : [{ role: 'viewMenu' } as const]),
    { role: 'windowMenu' },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

let webRoot = ''

async function start(): Promise<void> {
  await app.whenReady()
  const layout: Layout = resolveLayout({
    packaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    appRoot: path.resolve(__dirname, '..'),
  })
  webRoot = layout.webRoot
  const dirs: DataDirs = dataDirs(app.getPath('userData'))
  for (const dir of [dirs.data, dirs.models, dirs.ollamaModels, dirs.ollamaHome, dirs.logs]) {
    fs.mkdirSync(dir, { recursive: true })
  }

  const [ollamaPort, apiPort] = await twoFreePorts()
  const ports: Ports = { ollama: ollamaPort, api: apiPort }

  buildMenu()
  lockDownSession(apiUrl(ports))
  mainWindow = createWindow(apiUrl(ports))
  void mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(startPage(systemLocale()))}`)

  const missing = [layout.ollamaBinary, layout.apiBinary, layout.whisperBinary, layout.webRoot].filter(
    file => !fs.existsSync(file),
  )
  if (missing.length > 0) {
    showFatal(
      say(systemLocale(), 'dialog.incomplete'),
      say(systemLocale(), 'dialog.missingParts', { files: missing.join(', ') }),
      dirs.logs,
    )
    return
  }

  await reapOrphans(dirs.pidFile)

  const onFatal = (service: string, reason: string): void => {
    if (quitting) return
    showFatal(say(systemLocale(), 'dialog.stopped', { service }), reason, dirs.logs)
  }
  const ollama = new Service(
    {
      name: 'ollama',
      command: layout.ollamaBinary,
      args: ['serve'],
      env: ollamaEnv(ports, dirs, process.env),
      healthUrl: `${ollamaUrl(ports)}/api/version`,
      logFile: path.join(dirs.logs, 'ollama.log'),
      startTimeoutMs: OLLAMA_START_TIMEOUT_MS,
      pidFile: dirs.pidFile,
    },
    { onFatal },
  )
  const api = new Service(
    {
      name: 'api',
      command: layout.apiBinary,
      env: apiEnv(ports, dirs, layout, process.pid, process.env),
      healthUrl: `${apiUrl(ports)}/health`,
      logFile: path.join(dirs.logs, 'api.log'),
      startTimeoutMs: API_START_TIMEOUT_MS,
      pidFile: dirs.pidFile,
    },
    { onFatal },
  )

  try {
    await supervisor.startAll([ollama, api]) // Ollama first: the api checks it on start
  } catch (error) {
    await supervisor.stopAll()
    showFatal(
      say(systemLocale(), 'dialog.couldNotStart'),
      error instanceof Error ? error.message : String(error),
      dirs.logs,
    )
    return
  }
  if (mainWindow) void mainWindow.loadURL(`${APP_ORIGIN}/`)
}

app.on('window-all-closed', () => app.quit())

app.on('before-quit', (event) => {
  if (quitting) return
  quitting = true
  event.preventDefault()
  void supervisor.stopAll().finally(() => app.exit(0))
})

app.on('second-instance', () => {
  if (mainWindow?.isMinimized()) mainWindow.restore()
  mainWindow?.focus()
})

for (const signal of ['SIGINT', 'SIGTERM'] as const) process.on(signal, () => app.quit())

if (app.requestSingleInstanceLock()) {
  start().catch((error: unknown) => {
    dialog.showErrorBox(
      say(systemLocale(), 'dialog.couldNotStart'),
      error instanceof Error ? error.message : String(error),
    )
    app.exit(1)
  })
} else {
  app.quit()
}
