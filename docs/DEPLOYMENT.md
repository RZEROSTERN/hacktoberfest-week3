# Deployment guide: Linux, Mac App Store and Windows

PostCall (package id `mx.dev1.postcall`) ships today as one build: an ad-hoc signed macOS Apple Silicon `.dmg`
(`make desktop-dist`, see [README.md](../README.md)). This guide is the plan for three more ways to deploy it. **None
of them has been built or run.** Everything here comes from reading the code, the official documentation and
Apple's, Ollama's and Microsoft-side sources listed at the end. Each claim is marked:

- **Verified**: read in the cited source, or measured in this repository.
- **Unverified**: reasoning or common practice that must be tested before relying on it.

## 1. Where things stand

| Target | Can it be done? | Main blockers | Rough effort (one person) | Suggested order |
| --- | --- | --- | --- | --- |
| **Windows** (installer) | Yes | Process control, API shutdown and memory check use POSIX-only calls; audio decoding uses a macOS tool; 1.4 GB of Ollama GPU libraries; code signing | 5 to 8 days | 1st: the biggest audience of freelancers |
| **Linux** (AppImage, `.deb`, `.rpm`) | Yes | Audio decoding; 1.4 GB Ollama archive; Chromium sandbox on Ubuntu 24.04; GPU support varies by machine | 3 to 5 days | 2nd: the code is closest to what already runs |
| **Mac App Store** | Possible, with the highest risk | App Sandbox with four native child programs and local servers; the 7 GB model download against Apple's rule 2.4.5(iv); no license keys; PyInstaller `--onefile` | 5 to 10 days plus review rounds | Last: prototype the unknowns first (section 4.5) |

The effort figures are my estimates, not measurements. Two things come before any of the three and are the same work for
all: the shared porting list in section 2, and deciding the open questions in section 7 (certificates cost money, and
some choices change the product).

**What the Mac build already gives the others:** the architecture (an Electron shell starting Ollama and the API on
loopback ports), the web app (platform independent), the API (Python, mostly portable), the tests, and the real-app
checks. What it does not give: any measurement on a machine other than an Apple M2 Pro. The speed targets in
[BENCHMARKS.md](BENCHMARKS.md) (a 30-minute call transcribed in under 10 minutes, notes plus proposal in under 3)
were met on Metal; a CPU-only Windows or Linux laptop may miss them, and that is a product question, not only an
engineering one.

## 2. Shared work for every non-macOS target

These are the places where the code assumes macOS or POSIX. File and line numbers are from the current `develop`.

| # | What | Where | Why it breaks | What to do |
| --- | --- | --- | --- | --- |
| 1 | Audio decoding | `api/app/audio.py:24-27` | Calls `afconvert`, which ships only with macOS. | Add a second decoder behind the existing `Decoder` protocol (`jobs.py` already depends on the protocol, not on afconvert). Options: bundle an FFmpeg build and convert to 16 kHz mono WAV, or build whisper.cpp with `-DWHISPER_COMMON_FFMPEG=yes` (a flag its README lists for the examples; unverified for `whisper-cli`). FFmpeg is LGPL or GPL depending on how it is built: use an LGPL configuration and add it to `THIRD_PARTY_NOTICES.md`. |
| 2 | Stopping child programs | `desktop/src/supervisor.ts:31,74,77,91,136`, `desktop/src/pidfile.ts:40` | Uses process groups: `detached: true` plus `process.kill(-pid)`. **Verified** (Node docs): on Windows `detached` gives the child its own console window instead, and `SIGTERM`, `SIGKILL` and `SIGINT` all terminate the process "forcefully and abruptly", so the "stop politely, force after 8 s" sequence does not exist there. | Windows: start children with `windowsHide: true` and stop the tree with `taskkill /PID <pid> /T /F` or a Job Object. Linux: works as is. |
| 3 | Finding a leftover process after a force quit | `desktop/src/pidfile.ts:32` | Reads the command line with `ps -p`, which Windows does not have. | Windows: `tasklist` or PowerShell `Get-CimInstance Win32_Process`. Linux: works as is. |
| 4 | API watching the desktop app | `api/app/lifecycle.py:10` | `os.kill(pid, 0)` is the POSIX "does it exist" check. **Verified** (Python docs): on Windows any signal other than `CTRL_C_EVENT` and `CTRL_BREAK_EVENT` "will cause the process to be unconditionally killed by the TerminateProcess API", with the signal number as exit code. So the API would terminate the desktop app every two seconds. **This is a blocker, not a cosmetic issue.** | Replace with a check that does not signal (`psutil.pid_exists`, or `OpenProcess` through `ctypes`). Add a test that runs on Windows. |
| 5 | API shutting itself down | `api/app/__main__.py:17` | `os.kill(os.getpid(), SIGTERM)` is abrupt on Windows (same Python docs), so uvicorn does not shut down cleanly and a running transcription is not stopped gracefully (it is still marked "interrupted" on the next start). | Ask uvicorn to stop (`server.should_exit = True`) instead of signalling yourself. |
| 6 | Total memory | `api/app/system.py:7` | `os.sysconf("SC_PHYS_PAGES")` exists only on Unix (**verified**: the Python docs give its availability as "Unix"). On Windows it raises `AttributeError`, which would break the model request screen. | `psutil.virtual_memory().total`, or `GlobalMemoryStatusEx` through `ctypes`. |
| 7 | Program names | `desktop/src/layout.ts:16-18,26-28` | Windows programs end in `.exe`. | Choose the name by `process.platform`. |
| 8 | whisper-cli | `desktop/scripts/build-whisper.sh:26-27` | macOS only (Metal, `CMAKE_OSX_*`). whisper.cpp publishes no prebuilt programs for any desktop system (**verified**: its latest release, v1.9.5, has no attached files, and its README offers Docker images and Conan). | One build script per OS. Flags per its README: `-DGGML_CUDA=1`, `-DGGML_VULKAN=1`, `-DGGML_HIP=1`; plain `cmake -B build` for CPU. Keep the pinned revision. |
| 9 | Ollama | `desktop/scripts/fetch-ollama.sh:16-21,37` | Downloads the darwin archive only. | One fetch script per OS; pin each archive's SHA-256 from the release's `sha256sum.txt` asset. See sections 3 to 5 for what the archives contain. |
| 10 | PyInstaller | `api/postcall-api.spec`, `Makefile` target `build-api` | **Verified** (PyInstaller docs): "you must install PyInstaller on each platform and bundle your app separately on each." | Build the API on each target OS (see CI, section 6). |
| 11 | Packaging config | `desktop/electron-builder.yml` | Has only a `mac:` block and `extraResources` paths for macOS. | Add `linux:` and `win:` blocks. Put each platform's programs under their own folder (for example `desktop/build/<os>-<arch>/`) and keep one config file per platform, chosen with `electron-builder --config <file>` (flag **verified** in `electron-builder --help`; so are `--linux`, `--win`, `--mac`, `--x64`, `--arm64`, `--dir`). |
| 12 | The real-app checks | `desktop/scripts/shell-check.mjs`, `full-flow.mjs`, `layout-check.mjs` | `shell-check.mjs` uses `ps` and `lsof`; the scripts assume `.app` paths. | Port the process and port inspection per OS; the page-level checks (CDP) are portable. |
| 13 | Memory figures in the model list | `api/data/models.json` | The `ram_gb` figures come from one Mac. | Re-measure on each platform's reference machines before keeping them. |

Also, for every platform:

- **No automatic updates in the first version.** The privacy rule is that the only network traffic is the model
  download the user approves. An updater makes the app contact a server on its own. If you want one, make it opt-in
  and say so in the README's Privacy section. (Electron's `autoUpdater` is disabled in Mac App Store builds anyway,
  section 4.)
- **Where data lives.** Electron's `userData` is `~/Library/Application Support/PostCall` on macOS,
  `%APPDATA%\PostCall` on Windows and `~/.config/PostCall` on Linux. The models take about 7.2 GB there, so an
  uninstaller must ask before deleting them.
- **Versions.** `mx.dev1.postcall` and the version number must match on every platform. Changing the id after a
  public release makes the operating system treat it as a different app.
- **Notices.** Add each platform's extra components to `THIRD_PARTY_NOTICES.md` (FFmpeg, the CUDA/ROCm/Vulkan libraries
  that ship inside Ollama's archives, the Visual C++ runtime if you bundle it). Review NVIDIA's and AMD's
  redistribution terms for the libraries inside Ollama's archives before you ship them: **unverified**.

## 3. Linux

### 3.1 Formats

| Format | Use | Notes |
| --- | --- | --- |
| `.deb` | Ubuntu, Debian, Mint | Supports `depends`, install scripts and an AppArmor profile (`deb.appArmorProfile`, "File path to custom AppArmor profile (Ubuntu 24+)", **verified** in the schema). Preferred on Ubuntu 24.04, see 3.3. |
| `.rpm` | Fedora, openSUSE | Same options as `.deb` (`rpm.depends`, `rpm.appArmorProfile`). |
| AppImage | Everything else | Needs FUSE 2 at run time (**verified**, AppImage wiki): on Ubuntu 22.04 install `libfuse2`; the package is named `libfuse2t64` on 24.04; newer AppImages may bundle FUSE 3. Publish that line next to the download. |
| Flatpak, Snap | Later | electron-builder has targets for both. Their sandboxes restrict local servers and child programs; **not evaluated**. |

### 3.2 What to build

1. Build on the oldest Linux you want to support (for example Ubuntu 22.04): programs built on a newer glibc will not
   run on an older one (**unverified**, common practice). electron-builder documents a Docker image for Linux builds
   on any host.
2. **Ollama.** The Linux release assets are `.tar.zst` archives (**verified**, release v0.35.1 asset list, and the
   [Linux docs](https://docs.ollama.com/linux)): `ollama-linux-amd64.tar.zst` (1372 MiB), `ollama-linux-arm64.tar.zst`
   (1489 MiB) and `ollama-linux-amd64-rocm.tar.zst` (1004 MiB, an addition for AMD). The beginning of the amd64
   archive was read: it extracts to `bin/ollama` and `lib/ollama/` and the first large file is
   `lib/ollama/cuda_v12/libggml-cuda.so`. Keep that `bin/` + `lib/ollama/` layout inside the app's resources, because
   Ollama's docs refer to `/usr/lib/ollama` and the program is expected to find its libraries next to it
   (**unverified** for a relocated copy: test it, as was done for the macOS copy).
3. **Size.** The archive is dominated by GPU libraries. The macOS archive is 152 MiB. A Linux `.deb` will be about
   1.6 GB. Choose one (decision in section 7): ship it whole; ship without the CUDA/ROCm folders and accept CPU
   (and Vulkan, if present) only; or download the GPU libraries on first launch with the same approval screen as the
   models (this breaks "everything is bundled" but not the privacy rule).
4. **GPU.** Ollama's docs say NVIDIA needs CUDA installed on the machine (check with `nvidia-smi`) and AMD needs ROCm v7.
   Without them Ollama runs on the CPU. Gemma 4 E4B on CPU has not been timed; do that before promising anything.
5. **whisper-cli.** `cmake -B build` for CPU; add `-DGGML_VULKAN=1` or `-DGGML_CUDA=1` for GPUs. A CPU build is the safe default.
6. **API.** `uv run pyinstaller` on the Linux builder. Prefer `--onedir`, see 6.2.

### 3.3 The Chromium sandbox on Ubuntu 24.04

The window runs with `sandbox: true` and that must not change. **Verified** (Ubuntu bug reports and the AppArmor
tracker, linked below): Ubuntu 24.04 restricts unprivileged user namespaces through AppArmor, and Electron apps then
fail at start with a SUID sandbox helper error. The proper fix is an AppArmor profile that allows the app's namespaces
(shipped by the `.deb` through `appArmorProfile`); the workarounds `--no-sandbox` and a system-wide sysctl weaken
security and are not acceptable here. For AppImage users, document the symptom and point them to the `.deb`.

### 3.4 Sketch of the configuration (option names verified in the installed electron-builder 26.15.3)

```yaml
# desktop/electron-builder.linux.yml (sketch; extends what electron-builder.yml has today)
appId: mx.dev1.postcall
productName: PostCall
linux:
  target: [AppImage, deb, rpm]
  category: Office
  maintainer: Marco Ramírez
  synopsis: Turn a recorded client call into a draft proposal, on this computer
deb:
  appArmorProfile: build/linux/postcall.apparmor   # a profile you write and test on Ubuntu 24.04
```

### 3.5 Test and release

Test on Ubuntu 22.04 and 24.04, Fedora and Debian, on a machine without a GPU and one with NVIDIA, with the system
Ollama stopped (the same rule as macOS). Publish the three files and their SHA-256 sums on the GitHub Release. No code
signing is required by the platform.

## 4. Mac App Store

Read this section as a **feasibility and risk assessment**, not a recipe: App Review decides, and several points
cannot be tested without an Apple Developer account.

### 4.1 Prerequisites (verified in Electron's Mac App Store guide)

- An Apple Developer Program membership (annual fee; see Apple's page for the current price).
- Certificates: **Apple Distribution** for the store; **Apple Development** for testing on registered Macs. (Developer ID
  certificates are for distribution outside the store.)
- An App ID for `mx.dev1.postcall`, a provisioning profile for testing, and an app record in App Store Connect.
- The MAS build of Electron. Upload with Apple Transporter. The guide does not describe building the `.pkg`;
  electron-builder's `mas` target does, and its schema has the installer-certificate options (`cscInstallerLink`,
  `cscInstallerKeyPassword`): **unverified** which certificate name App Store Connect expects, check when you get there.

### 4.2 The sandbox, and what it means for this app

Apps in the store "must run under Apple's App Sandbox". The Electron guide lists these entitlements (**verified**):

| File | Keys |
| --- | --- |
| Parent (the app) | `com.apple.security.app-sandbox` = true; `com.apple.security.application-groups` = `TEAM_ID.mx.dev1.postcall`; for listening sockets `com.apple.security.network.server`; for outgoing connections `com.apple.security.network.client`; for the open and save dialogs `com.apple.security.files.user-selected.read-write` |
| Child (every program in the bundle) | `com.apple.security.app-sandbox` = true; `com.apple.security.inherit` = true |

PostCall needs `network.server` (Ollama and the API listen on loopback), `network.client` (model downloads) and
user-selected file access (upload and export). Also, `crashReporter` and `autoUpdater` are disabled under the sandbox
(**verified**), so updates come from the store.

### 4.3 Blockers and risks

| # | Issue | Evidence | What to do |
| --- | --- | --- | --- |
| 1 | **The models are downloaded after install.** Rule 2.4.5(iv): Mac App Store apps "may not download or install standalone apps, kexts, additional code, or resources to add functionality or significantly change the app from what we see during the review process." The app is useless without its 7 GB of models. | **Verified** (App Review Guidelines). Model files are data, not code, but the rule says "resources", and nothing there grants an exception. In its favour, rule 4.2.3(ii) accepts a download at first launch if the app "disclose[s] the size of the download and prompt[s] users", which the request screen does. | Either ask App Review before building more, or ship a store edition that **bundles** the recommended models (Apple lists 200 GB as the maximum for macOS apps, **verified**; users download about 7.2 GB from the store; rule 2.4.5(ii) wants "self-contained, single app installation bundles"). The wizard and Settings can still offer other models. |
| 2 | **Code outside the bundle.** The API is a PyInstaller `--onefile` program that unpacks itself into a temporary folder and runs from there. | Rule 2.5.2 (**verified**): apps "should be self-contained in their bundles" and may not "download, install, or execute code which introduces or changes features". PyInstaller's docs confirm the unpacking (**verified**). | Use `--onedir` so every file is inside the signed bundle. |
| 3 | **Four native programs under the sandbox.** `ollama` (which starts `llama-server`), `postcall-api`, `whisper-cli` and their libraries must be signed with the child entitlements, inside the bundle. | The Electron guide says the child entitlements "must be added to the binaries and helpers in the app's bundle". electron-builder's `mas` block has `binaries` for extra programs to sign. | Prototype first (4.5). Unknowns: Metal compute and memory mapping of 6.6 GB under the sandbox, loopback servers started by child programs, and `afconvert` (and, later, an FFmpeg program) being executed from a sandboxed process. |
| 4 | **Orphan cleanup.** The pid-file reaper uses `ps` and process groups. | Rule 2.4.5(iii) (**verified**): apps may not "spawn processes that continue to run without consent after a user has quit the app". The app stops everything on quit and the API stops itself within 2 s, so the rule is met in normal use. | Check that `ps` and group signals work inside the sandbox; if not, rely on the API's own parent watcher and make Ollama stop on its own. |
| 5 | **License keys.** The pricing idea in the README is a one-time license. | Rule 2.4.5(vi) (**verified**): apps "may not ... require license keys, or implement their own copy protection". | In the store, sell it as a paid app (or in-app purchase). Keep the key-based license for direct sales only. |
| 6 | **Updates** | `autoUpdater` is disabled in MAS builds (**verified**). | Updates through the store. |
| 7 | **Privacy answers** | App Store Connect asks what data is collected. | "None": nothing leaves the Mac except the model downloads the user approves. Say which hosts those are (Ollama's registry, Hugging Face). |

### 4.4 Sketch of the configuration (option names verified in the installed schema; values to be confirmed)

```yaml
# desktop/electron-builder.mas.yml (sketch)
appId: mx.dev1.postcall
productName: PostCall
mas:
  type: distribution
  category: public.app-category.productivity
  minimumSystemVersion: "14.0"
  entitlements: build/entitlements.mas.plist            # the parent keys of 4.2
  entitlementsInherit: build/entitlements.mas.inherit.plist   # the child keys of 4.2
  provisioningProfile: build/postcall.provisionprofile
  binaries:                                              # every extra Mach-O file to sign (path format: check electron-builder's docs)
    - Contents/Resources/ollama/ollama
    - Contents/Resources/ollama/llama-server
    - Contents/Resources/api/postcall-api
    - Contents/Resources/whisper/whisper-cli
```

Build with `electron-builder --mac mas`. Because the bundled Ollama and the other programs were signed by someone else
or ad hoc, re-sign all of them with your Apple Distribution identity and the child entitlements (the macOS build
already lets electron-builder re-sign them ad hoc; that part works, **verified** here).

### 4.5 Do this before anything else

Build a throwaway sandboxed app with **development** signing (`mas-dev`) on your own Mac and answer four questions:
1. Does Ollama run a model on the GPU from inside the sandbox?
2. Can the API and Ollama listen on loopback and be reached by the window?
3. Can the app run `afconvert` (or a bundled FFmpeg) and `whisper-cli`?
4. Does quitting stop everything?

If any answer is no and cannot be fixed with an entitlement, the store edition is not viable and the money for the
membership is better spent on the Developer ID path below.

### 4.6 The Mac path outside the store (Developer ID and notarization)

Recommended **before** the store, and useful on its own: it removes the "Open Anyway" steps from the README. It needs
the same Apple Developer membership and a **Developer ID Application** certificate. electron-builder reads the
notarization credentials from environment variables (**verified**, schema): `APPLE_API_KEY`, `APPLE_API_KEY_ID` and
`APPLE_API_ISSUER`, or `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD` and `APPLE_TEAM_ID`, or `APPLE_KEYCHAIN` and
`APPLE_KEYCHAIN_PROFILE`. Then replace `identity: "-"` and `hardenedRuntime: false` in `electron-builder.yml`. With the
hardened runtime on, Electron needs entitlements such as `com.apple.security.cs.allow-jit` (the schema warns the app
may crash without them on arm64 with Electron 20 and newer), and the PyInstaller program and Ollama's Metal libraries
will each need their own entitlements and signing: follow the macOS code-signing section of PyInstaller's docs and
test the signed app with the same real-app checks (**unverified** here: it needs the certificate).

## 5. Windows

### 5.1 What to build

1. **Installer.** NSIS (`nsis` target) is the usual Windows installer in electron-builder. Options that matter
   (verified in the schema): `oneClick`, `perMachine`, `allowToChangeInstallationDirectory`, and
   `deleteAppDataOnUninstall` (one-click installers only: the 7 GB of models must not be deleted without asking, so
   prefer an assisted installer with a custom uninstall page through `include`).
2. **Size.** `ollama-windows-amd64.zip` is 1402 MiB and holds "only the Ollama CLI and GPU library dependencies for
   Nvidia" (**verified**, [Windows docs](https://docs.ollama.com/windows) and release assets). Add Electron (about 250
   MB) and the installer will be about 1.7 GB. NSIS has historically had a 2 GB installer limit (**unverified**: check
   before relying on it); the `nsis-web` target ("Web installer") downloads the application package at install time and
   is the escape hatch. The same trade-offs as Linux apply (ship whole, trim the GPU libraries, or download them).
   `ollama-windows-amd64-rocm.zip` (244 MiB) is the AMD addition; an `ollama-windows-arm64.zip` (200 MiB) exists in the
   release assets although the docs page does not list it.
3. **Ollama.** The docs state the zip "lets you embed Ollama in existing applications" (**verified**). Requirements:
   Windows 10 22H2 or newer; NVIDIA driver 551.61 or newer, or an AMD ROCm or Vulkan driver. Models default to
   `%HOMEPATH%\.ollama`; the app already sets its own `OLLAMA_MODELS`.
4. **whisper-cli.** Build with CMake and MSVC (the README lists Windows MSVC and MinGW as supported; **unverified**
   that its CPU build is fast enough, and the CUDA and Vulkan flags are the ones in 2, row 8).
5. **API.** Build with PyInstaller on Windows. `--onefile` programs are often flagged by antivirus products
   (**unverified**, widely reported): prefer `--onedir` and sign every executable.
6. Do all the code changes in section 2, rows 1 to 7. Rows 4 and 5 are the dangerous ones.

### 5.2 Signing

- **Without signing** the app installs, but Windows SmartScreen warns that it is from an unknown publisher
  (**unverified**, common behaviour), the Windows equivalent of the macOS first-open steps.
- **With electron-builder 26.15.3** (the version in this repository): `win.signtoolOptions` (a `.pfx` through
  `CSC_LINK`, or `certificateSubjectName` for EV hardware tokens, plus `rfc3161TimeStampServer`) or
  `win.azureSignOptions` (`endpoint`, `codeSigningAccountName`, `certificateProfileName`, `publisherName`;
  authenticates with Microsoft Entra ID variables). All names **verified** in the installed schema.
- **electron-builder 27 changes this**: both keys are replaced by one `win.sign` with a `type` (`signtool`, `hsm`,
  `pkcs11` or `azure`), and its docs mark the Azure integration as beta (**verified**, v27 breaking-changes page).
  Pin the version you build with and re-read its Windows signing page when upgrading.
- Even a signed app builds SmartScreen reputation over time; an EV certificate or Azure's service helps most. Check
  Microsoft's current eligibility rules for Azure Trusted Signing before planning on it: **unverified**.
- **Microsoft Store** (`appx` target): optional, built only on Windows 10 or newer (**verified**, schema), needs a
  Partner Center account. **Not evaluated** here.

### 5.3 Test and release

Test on Windows 10 22H2 and Windows 11, with and without an NVIDIA GPU, on a clean user profile, with a long path in the
user name, and with a corporate antivirus if you can. The real-app checks need the changes in section 2, row 12.

## 6. Build and release pipeline

There is no CI in the repository yet. Everything below is a proposal.

### 6.1 Build hosts

PyInstaller cannot cross-build (verified), so each platform needs its own host. electron-builder can build some
targets from another OS (its Linux Docker image is documented), but the API and `whisper-cli` still need the native one.

| Job | Host | Produces | Needs |
| --- | --- | --- | --- |
| macOS | macOS on Apple Silicon | `.dmg` (and `mas`) | Apple certificates and notarization variables, if signed |
| Windows | Windows | NSIS installer | MSVC, CUDA toolkit if you build a CUDA `whisper-cli`, a signing certificate or Azure account |
| Linux | Ubuntu 22.04 | AppImage, `.deb`, `.rpm` | CMake, a compiler, optionally the CUDA toolkit |

Each job runs the same steps: lint, typecheck and test (`make lint typecheck test`), build the web app, build the API,
build `whisper-cli`, fetch the pinned Ollama, `electron-builder` for that platform, then the real-app checks against the
installed result. Secrets (certificates, Apple and Azure credentials) belong in the CI provider's secret store, never
in the repository.

### 6.2 Decisions that apply to all builds

- **API as `--onedir`** everywhere except the plain macOS `.dmg`, where `--onefile` works today. A folder avoids the
  unpack on every start, antivirus flags and Mac App Store rule 2.5.2.
- **Pin and checksum** every downloaded input (Ollama archives against their `sha256sum.txt`, whisper.cpp by revision).
- **One release per tag**: build all platforms from the same commit, set `artifactName` (an option each platform block
  has, **verified**) so the files follow `PostCall-<version>-<os>-<arch>.<ext>` (the macOS one already looks like
  that by default), and publish SHA-256 sums.

### 6.3 Release checklist (per platform)

1. `develop` is green; `release/<version>` merged into `master`; tag `v<version>`.
2. Build on the platform's host from the tag.
3. Install on a clean machine or account with the system Ollama stopped.
4. Run the first-launch wizard (real downloads), the compatibility check, then upload to export, then quit and confirm
   no process is left (`desktop/scripts/full-flow.mjs` and `shell-check.mjs`, once ported).
5. Check the layout at the window sizes in `desktop/scripts/layout-check.mjs`.
6. Publish to GitHub Releases with sums and the install notes for that platform (Open Anyway on macOS without a
   certificate, SmartScreen on Windows without one, FUSE and AppArmor on Linux).

## 7. Decisions needed from you

1. **Which platforms, in what order.** My suggestion: Windows, then Linux, then the Mac signing path, and the store last.
2. **Money.** Apple Developer Program (needed for notarization and for the store), a Windows signing option (certificate
   or Azure), nothing for Linux.
3. **GPU libraries on Windows and Linux:** ship Ollama whole (about 1.4 GB heavier), ship CPU only, or download the GPU
   libraries on first launch with the user's approval.
4. **Store edition:** bundle the models (7.2 GB package) or ask App Review first. And accept that the store sells the
   app as a paid app, not with license keys.
5. **Updates:** none in the first version (recommended), or opt-in.
6. **Hardware promises:** after benchmarking CPU-only and GPU machines, decide the minimum and recommended hardware per
   platform for the README.
7. **The id `mx.dev1.postcall`:** confirm that you control `dev1.mx`, or accept that the id is a name only; either way it
   is permanent once published.

## Sources

- Electron: [Mac App Store Submission Guide](https://www.electronjs.org/docs/latest/tutorial/mac-app-store-submission-guide)
- Apple: [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) (2.4.5, 2.5.2, 4.2.3);
  [Maximum build file sizes](https://developer.apple.com/help/app-store-connect/reference/maximum-build-file-sizes) (macOS: 200 GB)
- Ollama: [Linux](https://docs.ollama.com/linux), [Windows](https://docs.ollama.com/windows),
  [release v0.35.1 assets](https://github.com/ollama/ollama/releases/tag/v0.35.1)
- whisper.cpp: [README (build and GPU backends)](https://github.com/ggml-org/whisper.cpp)
- Python: [`os.kill`](https://docs.python.org/3/library/os.html#os.kill); Node.js: [`child_process`](https://nodejs.org/api/child_process.html)
- PyInstaller: [Usage](https://pyinstaller.org/en/stable/usage.html)
- electron-builder: [Code signing for Windows](https://www.electron.build/docs/features/code-signing/code-signing-win/),
  [v27 breaking changes](https://www.electron.build/docs/migration/v27-breaking-changes/); option names read from the
  installed 26.15.3 schema
- AppImage: [FUSE](https://github.com/AppImage/AppImageKit/wiki/FUSE)
- Ubuntu 24.04 and Electron: [AppArmor bug list](https://lists.ubuntu.com/archives/ubuntu-mozillateam-bugs/2024-October/180500.html),
  [AppArmor tracker, issue 394](https://gitlab.com/apparmor/apparmor/-/issues/394)
