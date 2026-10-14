---
paths:
  - "desktop/**"
---

# Desktop rules

- Security stays as is: `contextIsolation` on, `nodeIntegration` off, `sandbox` on, devTools only when
  unpackaged, one preload value (`apiBase`) through `contextBridge`. Never load remote content: pages come
  from `app://postcall`, requests are limited to it and the local api, the CSP allows inline scripts only by
  hash, and only `https://ollama.com` may be opened in the user's browser.
- Always the bundled Ollama, started with a whitelisted environment (`env.ts`), `OLLAMA_HOST` on 127.0.0.1,
  its own `HOME` and models folder, `OLLAMA_NO_CLOUD=1`. Never read or start a system-wide one.
- Lifecycle: two free ports, Ollama first, then the api, wait for both health checks. Each child leads its own
  process group (kill the group: TERM, then KILL). A crashed service is restarted once, then a clear error.
  The pid file lets the next start clean up after a hard kill; the api also stops when the app is gone.
- The api, Ollama and whisper-cli binaries are inputs from `make desktop-resources`, never committed.
- Linux packages (experimental) are built only in a container: `desktop/linux/Dockerfile`, one stage per bundled
  piece, everything pinned by checksum or revision. Never bundle a macOS-built binary, and never use the host's
  `node_modules`, `.venv` or `desktop/build` in that build (the `.dockerignore` keeps them out). FFmpeg is built
  from source with no `--enable-gpl`; the build fails if that changes. Ollama's Linux layout (`bin/` + `lib/ollama/`)
  stays as it came (`layout.ts` knows both layouts).
- Pin versions and checksums of what is downloaded for bundling (`scripts/fetch-ollama.sh`, `build-whisper.sh`).
- Changing the packaged app: run `make desktop-dist`, then `desktop/scripts/shell-check.mjs` with `APP_BIN`
  pointing at an installed copy. Unit tests do not show whether the signed bundle still launches.

## Commands (repo root)
- `make desktop-setup` once; `make desktop-resources` builds web, api, whisper-cli and fetches Ollama
- `make desktop-dev` runs the shell from the repo; `make desktop-dist` builds `desktop/release/*.dmg`
- `make desktop-check` starts the shell for real and checks processes, ports, isolation and quitting
- `make linux-packages` (`LINUX_ARCH=arm64|amd64`) builds the `.deb` and `.rpm` in Docker into `desktop/release-linux/`;
  `sh desktop/linux/verify.sh <arch> <image>` installs one in a clean container and runs `shell-check.mjs` on it
- In `desktop/`: `npm run lint`, `npm run typecheck`, `npm test`

## Gotchas
- VS Code terminals set `ELECTRON_RUN_AS_NODE`, which makes Electron behave as plain Node: unset it when
  starting the app from a script. The packaged app turns that fuse off.
- In the main process `new URL('app://x').origin` is `"null"`: compare protocol and host.
- `Runtime.evaluate` over the DevTools protocol ignores the page's CSP: test the policy via the header and
  `securitypolicyviolation`, not with `eval()`.
- To signal the app, kill the real Electron binary, not `node_modules/.bin/electron` (a Node wrapper).
- electron-builder turns rpm `xz` into multi-threaded `xzmt`, which ran out of memory on a 7.7 GB Docker VM with the
  Ollama GPU libraries: `rpm.compression: gzip` is the value that passes through.
- The build is ad-hoc signed (`identity: "-"`, no hardened runtime): Apple Silicon refuses unsigned code.
- Always start the app with `--user-data-dir=<scratch folder>` when testing: it ignores a changed `HOME` and
  otherwise writes into `~/Library/Application Support/PostCall`, the real data folder of an installed app.
- The shell's own strings (start page, error dialogs) are in `src/messages.ts` for the eleven languages and follow the
  system language; `locale.test.ts` checks every language has every message. Technical details in a dialog stay English.
- A regex written inside the template literal passed to `page.eval` loses its backslashes (`\b` becomes a backspace,
  `\s` becomes `s`) and fails silently. Collect text in the page and match it in Node, outside the template.
