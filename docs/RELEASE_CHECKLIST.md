# Release checklist: try the installers on the three real machines

CI proves that each installer builds and that the programs inside it start and can transcribe a short call (see
[DECISIONS.md](DECISIONS.md)). It cannot open a window, click through a warning, download 7 GB of models or watch a
graphics card. This checklist is that part, done by hand, on the three machines the release is meant for:

| Machine | System | Installer | What it mainly tests |
| --- | --- | --- | --- |
| **A** MacBook Pro M2 Pro | macOS | `PostCall-<version>-arm64.dmg` | Gatekeeper, Metal, the reference speeds |
| **B** PC with a Ryzen 9 and an NVIDIA GeForce | Windows 11 | `PostCall-<version>-x64-setup.exe` | SmartScreen, Vulkan on a real card, an accented user name, process cleanup |
| **C** Intel MacBook with Linux Mint | Linux Mint | `postcall_<version>_amd64.deb` **and** `PostCall-<version>-x86_64.AppImage` | AVX2, FUSE, the sandbox, CPU-only speed on modest hardware |

Test the files of the **draft release** (the ones that will be published), not an earlier build: builds are not
bit-for-bit identical from one run to the next, so the checksums differ. **Publish the draft only when every row of
every machine below is ticked or has a written reason.**

Use the sample call `samples/interview.mp3` (5 min 24 s, Spanish; its key facts are in `samples/interview.facts.json`):
<https://github.com/RZEROSTERN/hacktoberfest-week3/raw/master/samples/interview.mp3>.

## 0. Before you start (once per release)

- [ ] The draft release exists (created by the `Release (draft)` workflow from the tag), with four installers and
      `SHA256SUMS`. If CI was not available, see "If CI is down" in the README.
- [ ] On each machine: download only the file(s) for that machine and **check the checksum** against `SHA256SUMS`:
  - macOS: `shasum -a 256 ~/Downloads/PostCall-*.dmg` (or `shasum -a 256 -c SHA256SUMS --ignore-missing` in the folder)
  - Linux: `sha256sum -c SHA256SUMS --ignore-missing`
  - Windows (PowerShell): `Get-FileHash .\PostCall-*-setup.exe -Algorithm SHA256`, then compare with the line in `SHA256SUMS`
- [ ] Use a clean user account or a machine that has never had PostCall, so the first launch is a real first launch.
      (To start over on one account, delete the data folder listed under "Uninstall" for that system.)
- [ ] Note down each machine's OS version, CPU, graphics card and RAM in the results table at the end.

## 1. Machine A: macOS (Apple Silicon)

**Install and open (past Gatekeeper)**
- [ ] Open the `.dmg`, drag **PostCall** into **Applications**.
- [ ] Double-click it. macOS says it cannot verify the app: that is expected, the app is not signed. Click **Done**.
- [ ] **System Settings → Privacy & Security**, scroll to the message about PostCall, click **Open Anyway**, confirm.
      (From a terminal instead: `xattr -dr com.apple.quarantine /Applications/PostCall.app`.)
- [ ] PostCall opens and shows the model request screen. Nothing else in the app works yet, as designed.

**First launch and the models** (about 7.2 GB, use Wi-Fi)
- [ ] The screen shows Gemma 4 E4B as *Recommended*, the sizes, the memory each model needs, free disk and a Wi-Fi advice.
- [ ] *Not now* closes it, and it comes back on the next launch. Then *Download now*.
- [ ] The installer-style screen shows each step with a progress bar, size, speed and time left; the compatibility
      check passes; it ends at *Ready*. Pause and resume once. Quit mid-download and reopen: it resumes after asking.

**The full flow**
- [ ] Profile: fill in a name, a rate and terms; save.
- [ ] New proposal: upload `interview.mp3` (the recording reminder is shown). Transcription shows progress and ends with a
      timestamped transcript. Note the time.
- [ ] Notes and draft are generated. Note the time. Scope items link to a transcript moment; clicking shows the quote;
      items without a source are flagged as assumptions; the summary has no price; the price comes from the profile only.
- [ ] Edit a sentence, remove one item, export **Markdown** and **PDF**, and open both.
- [ ] Change the interface language to another one, then back.

**Quit and orphans**
- [ ] Quit with ⌘Q. Then: `ps aux | grep -E 'ollama|postcall-api|whisper-cli' | grep -v grep` prints nothing.
- [ ] Open again and, while it runs, force quit it (`kill -9` on the PostCall process). Within a few seconds
      `postcall-api` must be gone. Open the app again: the leftover Ollama is cleaned up.

**Uninstall**
- [ ] Drag PostCall to the Trash. The data stays in `~/Library/Application Support/PostCall` (about 7.2 GB of models):
      this is by design; delete the folder by hand to remove everything.

## 2. Machine B: Windows 11 (Ryzen 9, NVIDIA GeForce)

**Install and open (past SmartScreen)**
- [ ] Run `PostCall-<version>-x64-setup.exe`. Windows shows "Windows protected your PC": click **More info**, then **Run anyway**.
- [ ] The installer asks for a folder (the default is under `AppData\Local\Programs`) and does not ask for administrator rights.
- [ ] Open PostCall from the Start menu. Windows Defender may scan it the first time, so allow up to a minute; note how long.
- [ ] No Windows Firewall prompt appears (PostCall only listens on 127.0.0.1). If one does, write it down.
- [ ] The model request screen appears.

**An accented user name** (the most likely Windows-only bug: the speech engine opens files by name)
- [ ] Create a second local user called `Ramírez` (Settings → Accounts → Other users), sign in to it, install and open
      PostCall there, and do the transcription step below. It must work like the first user.

**First launch, models, full flow, quit** — same checks as machine A, with these differences:
- [ ] While notes and draft are generated, look at **Task Manager → Performance → GPU**. Write down whether the
      NVIDIA card is busy (the engine uses Vulkan here, not CUDA), and the time taken. Open
      `%APPDATA%\PostCall\logs\ollama.log` and search for `vulkan` to see which device it chose.
- [ ] Transcription and generation times are in the results table (the speech engine runs on the CPU here).
- [ ] Close the window. In PowerShell: `Get-Process ollama,postcall-api,whisper-cli,ffmpeg,PostCall -ErrorAction SilentlyContinue`
      prints nothing.
- [ ] Open the app, then end the **PostCall** process from Task Manager (Details tab, *End task*). `postcall-api.exe`
      must disappear within seconds. Open the app again: any leftover `ollama.exe` is gone (`Get-Process ollama`).

**Uninstall**
- [ ] Settings → Apps → PostCall → Uninstall. The data in `%APPDATA%\PostCall` stays (the models are not deleted
      without asking); delete it by hand to remove everything. Reinstalling must find the models again.

## 3. Machine C: Linux Mint (Intel MacBook, no dedicated GPU)

**Before installing**
- [ ] `grep -m1 -o avx2 /proc/cpuinfo` prints `avx2`. If it prints nothing, the speech engine will stop with
      "Illegal instruction": note the CPU model (`lscpu | grep 'Model name'`) and stop here; this machine needs a build without AVX2.
- [ ] Note the Mint version (`cat /etc/os-release`; Mint 21 is based on Ubuntu 22.04, Mint 22 on 24.04).

**The `.deb`**
- [ ] `sudo apt install ./postcall_<version>_amd64.deb` finishes without asking for anything else, then PostCall is in
      the menu (and `postcall` runs it). No warning about an unsigned app appears on Linux.
- [ ] It opens and shows the model request screen. The memory advice for each model matches this machine's RAM.
- [ ] First launch, models, full flow: as on machine A. **Everything is CPU-only here**: write down the transcription
      time and the notes-and-draft time. Expect them to be much slower than on the Mac.
- [ ] Quit. `pgrep -a -f 'ollama|postcall|whisper-cli|ffmpeg'` prints nothing. Force quit and reopen as on machine A.
- [ ] `sudo apt remove postcall` removes the app. The data stays in `~/.config/PostCall`; delete it by hand.

**The AppImage** (after removing the `.deb`)
- [ ] Make it executable: `chmod +x PostCall-<version>-x86_64.AppImage` (or file manager → Properties → *Allow executing*), then run it.
- [ ] If it stops with an error about `libfuse.so.2`: `sudo apt install libfuse2` (`libfuse2t64` on Mint 22), then retry.
- [ ] If it stops with a sandbox error (Ubuntu 24.04 based systems restrict it), write down the exact text; the `.deb` is the answer for these systems.
- [ ] If it opens: repeat the quit-and-orphans check.

## Results to write down

| | Machine A (Mac) | Machine B (Windows) | Machine C (Mint) |
| --- | --- | --- | --- |
| OS version, CPU, GPU, RAM | | | |
| Installed and opened (what warning, how long) | | | |
| Model download (time, any retry) | | | |
| Transcription time, sample call | | | |
| Notes + draft time, sample call | | | |
| Full flow and both exports worked | | | |
| Processes left after quit / after force quit | | | |
| Uninstall left only the data folder | | | |
| Anything odd (with the log: `<data folder>/logs/api.log`, `ollama.log`) | | | |

For reference, the Mac M2 Pro measured 29 s to transcribe and 52 s for notes and draft on a quiet machine (74 s and
140 s on a busy one); nothing is measured yet for Windows or Linux, so these numbers are the first.

## Publishing

- [ ] Every row above is ticked or explained.
- [ ] Edit the draft's notes if needed (the generated text is a starting point), then **publish it by hand** from the
      Releases page. CI never publishes.
- [ ] Merge `master` back into `develop` (a pull request), as in the release process in the README.
