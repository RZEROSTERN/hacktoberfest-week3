# Trying PostCall on other systems: Ubuntu/Mint, AlmaLinux (RHEL family) and Windows

This is a hands-on guide for someone with a machine of one of these kinds (or for a Claude Code session started on
that machine, inside a clone of this repository). It says what to run, what to expect and what to send back. The plans
behind it are in [DEPLOYMENT.md](DEPLOYMENT.md); the stable app today is the macOS `.dmg` ([README](../README.md)).

Claims are marked like in DEPLOYMENT.md: **Verified** means checked and the way is stated; **Unverified** means it
must be tested on the machine. Dates are 2026-10-14.

| System | State | What you can do today |
| --- | --- | --- |
| Ubuntu, Debian, Linux Mint (x86-64 or ARM64) | The ARM64 `.deb` builds from source in a container; x86-64 not built yet; none installed on real hardware | Section 1: build it and try it |
| Fedora | The `.rpm` ran out of memory once while building; the fix is made but not yet tested | Section 2.1 |
| AlmaLinux, Rocky, RHEL (9 and 10) | Not supported yet; two problems found (section 2.2) | Section 2: check them on a real machine |
| Windows | **PostCall does not run on Windows yet** | Section 3: run the tests to get a measured list of what breaks |

Whatever the system, **do not download the models just to test the install** (7.2 GB) unless that is what you want to
test: the first-launch screen, the app opening and the processes starting are already a useful result.

## 1. Ubuntu, Debian and Linux Mint

Needs: Docker Engine with the buildx plugin (follow [Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/);
for Linux Mint the page says to use `UBUNTU_CODENAME` where it uses `VERSION_CODENAME`), about 25 GB of free disk and 8
GB of memory. The build uses every core for a while, so run it when you are not using the machine.

```sh
git clone https://github.com/RZEROSTERN/hacktoberfest-week3.git
cd hacktoberfest-week3 && git checkout feature/linux-packaging     # until it is merged into develop
sh desktop/linux/build.sh amd64 2>&1 | tee build-amd64.log         # arm64 on an ARM machine; expect 30 to 40 minutes (an estimate)
sudo apt install ./desktop/release-linux/amd64/postcall_*.deb
postcall                                                            # or open it from the menu
```

Also try it in clean containers (the same install a user would do, as an ordinary user, on a virtual display):
`sh desktop/linux/verify.sh amd64 ubuntu:22.04`, then `ubuntu:24.04` and `debian:12`.

Send back: `cat /etc/os-release`, `lscpu | grep -o -w avx2 | head -1` (the transcription engine is built for CPUs with
AVX2: **unverified** on older ones, where it would crash), `lspci | grep -iE 'vga|3d'`,
`sysctl kernel.apparmor_restrict_unprivileged_userns` (Ubuntu 24.04 and Mint 22 may restrict user namespaces; the
package installs an AppArmor profile for this, **unverified** on a real machine), whether the window opens and shows
the model request, and the end of `build-amd64.log` if the build failed.

## 2. AlmaLinux, Rocky Linux, RHEL (and other RHEL clones)

### 2.1 Fedora, for comparison

The `.rpm` is built by the same pipeline as the `.deb` (`desktop/release-linux/<arch>/postcall-*.rpm`).
`sudo dnf install ./postcall-*.rpm`, or `sh desktop/linux/verify.sh amd64 fedora:latest` for a clean container.

### 2.2 What is known about AlmaLinux 9 and 10

Checked on 2026-10-14 in the official `almalinux:9` (9.8) and `almalinux:10` (10.2) container images, with `ldd --version`
and `dnf repoquery` (**verified**). Rocky and RHEL follow the same major versions, but were not checked.

| | AlmaLinux 9 (RHEL 9) | AlmaLinux 10 (RHEL 10) |
| --- | --- | --- |
| C library (glibc) | 2.34 | 2.39 |
| Packages the `.rpm` requires: `gtk3 libnotify nss libXScrnSaver libXtst xdg-utils at-spi2-core libuuid` | all exist | **`libXScrnSaver` does not exist** in BaseOS, AppStream, CRB or extras |
| Virtual display for testing (`xorg-x11-server-Xvfb`) | exists | **does not exist** (RHEL 10 dropped the Xorg server) |

What follows, and what is **not** done yet:

- **AlmaLinux 10 / RHEL 10:** the C library is new enough, but `dnf install` of the current `.rpm` is refused because
  `libXScrnSaver` cannot be found. The list of required packages is electron-builder's default, which the project has
  not overridden yet. Whether Electron really needs that library (and whether a Wayland-only system can run the
  window) is **unverified**. The fix is probably to set `rpm.depends` in `desktop/electron-builder.yml` without it and
  test, but nobody has done that.
- **AlmaLinux 9 / RHEL 9:** every dependency exists, but the programs inside the package are built on Ubuntu 22.04
  (glibc 2.35), one version newer than RHEL 9 has. They fail to start **only if** they use a symbol that is new in
  2.35: **unverified**, and easy to check (below).
- A package that is sure to run on RHEL 9 needs the programs built on a RHEL 9 base. The Dockerfile uses Ubuntu with
  `apt`; a variant on `almalinux:9` with `dnf` is **not written**. Building on an AlmaLinux machine does not change this,
  because the build runs in the Ubuntu container whatever the host is.

### 2.3 What to run on an AlmaLinux 9 or 10 machine

Everything below is safe to try on a machine you do not mind putting a package of about 3 GB (once installed) on.

1. Get the package, by building it on another machine (section 1: `build.sh amd64` makes the `.rpm` too) or from the
   experimental pre-release once there is one. Copy the `.rpm` over.
2. Look before installing, which also shows the C library requirement:
   ```sh
   sudo dnf install -y binutils      # for objdump
   rpm -qpR postcall-*.rpm | sort -u # what it requires
   ```
3. Install it. Expect it to fail on AlmaLinux 10 with a message that nothing provides `libXScrnSaver`; copy the
   message. To go on anyway for a test only: `sudo rpm -ivh --nodeps postcall-*.rpm`.
4. Check the programs against this machine's C library:
   ```sh
   ldd --version | head -1
   for f in /opt/PostCall/postcall /opt/PostCall/resources/api/postcall-api \
            /opt/PostCall/resources/whisper/whisper-cli /opt/PostCall/resources/ffmpeg/ffmpeg \
            /opt/PostCall/resources/ollama/bin/ollama; do
     echo "== $f"; ldd "$f" 2>&1 | grep -E 'not found|version' ; objdump -T "$f" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1
   done
   ```
   The last line of each block is the newest C library version that program asks for. If any is above the machine's
   (2.34 on AlmaLinux 9), that program is what has to be rebuilt on a RHEL 9 base.
5. Start it: `/opt/PostCall/postcall` from a terminal in a graphical session, and copy any message it prints. Then
   check that nothing is left running after you close it: `ps aux | grep -E 'ollama|postcall'`.

Send back the output of steps 3 to 5, `cat /etc/os-release`, and `echo $XDG_SESSION_TYPE` (x11 or wayland).

## 3. Windows

**PostCall does not run on Windows today.** The port is planned ([DEPLOYMENT.md](DEPLOYMENT.md) section 5), and
several places in the code assume macOS or POSIX. The most serious is the api's check that the desktop app is still
alive: on Windows `os.kill(pid, 0)` does not test for the process, it terminates it (**verified** in the Python docs,
quoted in DEPLOYMENT.md section 2, row 4). The others are the stopping of child programs, the memory check on the
model screen, program names without `.exe`, and building whisper-cli, Ollama and the api for Windows.

So the useful thing a Windows machine can do now is give a **measured list of what breaks**, by running the existing
tests. The `Makefile` needs `make`, which Windows does not have, so these are the same commands typed by hand.

1. Install: [Git](https://git-scm.com/download/win), [Node.js 24](https://nodejs.org/) (what the project uses), and
   [uv](https://docs.astral.sh/uv/getting-started/installation/) (`winget install --id=astral-sh.uv -e`, or the
   PowerShell installer on that page). Open a new PowerShell window afterwards.
2. Run the tests, one part at a time, and keep the output:
   ```powershell
   git clone https://github.com/RZEROSTERN/hacktoberfest-week3.git
   cd hacktoberfest-week3
   git checkout feature/linux-packaging        # until it is merged into develop

   cd api;     uv sync;  uv run pytest -q 2>&1 | Tee-Object ..\windows-api.txt;     cd ..
   cd web;     npm ci;   npm test        2>&1 | Tee-Object ..\windows-web.txt;     cd ..
   cd desktop; npm ci;   npm test        2>&1 | Tee-Object ..\windows-desktop.txt; cd ..
   ```
3. What to expect (**unverified**, from reading the code): the web tests should pass, because they do not touch the
   system. In the api, tests that start the app's lifecycle watcher or ask for the machine's memory should fail, and a
   test run may end suddenly with no summary when the watcher terminates the test process itself; that is the blocker
   above, not a problem with your setup. In the desktop tests, anything that starts or stops processes will fail.
4. Send back the three text files, the Windows edition and version (`winver`), and whether the machine has an NVIDIA
   or AMD graphics card (`Get-CimInstance Win32_VideoController | Select-Object Name`).

When the port itself starts, the Windows machine also needs: Visual Studio Build Tools with the "Desktop development
with C++" workload and CMake (to build whisper.cpp, which lists MSVC as supported), the Windows build of Ollama (the
standalone `ollama-windows-amd64.zip`, 1.4 GB, is the one meant for embedding in an application, per its docs), and a
code-signing certificate decision (DEPLOYMENT.md section 5.2, and the questions in section 7). None of that is needed
for the test run above.

## Sending results

Paste them into a new GitHub issue on the repository, or hand them to the person doing the porting. Please include the
exact commands you ran and the whole error text; "it did not work" cannot be acted on, and a successful run with no
surprises is worth knowing too.
