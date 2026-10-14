// A stand-in for Ollama or the api: answers /health on PORT, and misbehaves on request.
//   CRASH_AFTER_MS   exit with code 1 this long after it started listening
//   NEVER_READY      never listen (a service that hangs while starting)
//   EXIT_AT_START    exit immediately
//   CHILD_PID_FILE   start a helper process in the same group and write its pid here
//   START_LOG        append a line here on every start (to count restarts)
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import http from 'node:http'

if (process.env.START_LOG) fs.appendFileSync(process.env.START_LOG, `${process.env.NAME ?? 'service'}\n`)
if (process.env.EXIT_AT_START) process.exit(3)
if (process.env.CHILD_PID_FILE) {
  const helper = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' })
  fs.writeFileSync(process.env.CHILD_PID_FILE, String(helper.pid))
}
if (!process.env.NEVER_READY) {
  http
    .createServer((_req, res) => {
      res.writeHead(200)
      res.end('ok')
    })
    .listen(Number(process.env.PORT), '127.0.0.1')
}
if (process.env.CRASH_AFTER_MS) setTimeout(() => process.exit(1), Number(process.env.CRASH_AFTER_MS))
setInterval(() => {}, 1000)
process.on('SIGTERM', () => process.exit(0))
