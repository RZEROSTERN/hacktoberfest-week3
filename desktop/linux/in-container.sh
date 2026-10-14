#!/bin/sh
# Runs INSIDE a throwaway container (see verify.sh). Installs the package the way a user would, checks that
# the package alone brought every library the app links against, then starts the app as an ordinary user on a
# virtual display and runs the lifecycle check (desktop/scripts/shell-check.mjs) against it.
#   in-container.sh <package-file> [check]      check: shell-check (default) or full-flow
set -eu
PKG=$1
CHECK=${2:-shell-check}
. /etc/os-release
echo "== $PRETTY_NAME, $(uname -m), glibc $(ldd --version 2>&1 | head -1 | awk '{print $NF}')"

# 1. Install just the package. Its dependencies must be enough on their own, which is why nothing else is
#    installed first (the virtual display would pull in libraries and hide a missing one).
case "$PKG" in
  *.deb)
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends "$PKG" >/tmp/install.log 2>&1 || { tail -20 /tmp/install.log; exit 1; } ;;
  *.rpm)
    dnf install -y -q "$PKG" >/tmp/install.log 2>&1 || { tail -20 /tmp/install.log; exit 1; } ;;
esac
echo "installed: $(du -sh /opt/PostCall | cut -f1) in /opt/PostCall"
missing=$(ldd /opt/PostCall/postcall | grep 'not found' || true)
[ -z "$missing" ] && echo "PASS | the package's dependencies cover every library the app links against" \
  || { echo "FAIL | missing libraries:"; echo "$missing"; exit 1; }
for f in /opt/PostCall/resources/ffmpeg/ffmpeg /opt/PostCall/resources/whisper/whisper-cli \
         /opt/PostCall/resources/api/postcall-api /opt/PostCall/resources/ollama/bin/ollama; do
  m=$(ldd "$f" 2>&1 | grep 'not found' || true)
  [ -z "$m" ] && echo "PASS | $(basename "$f") finds all its libraries" || { echo "FAIL | $f: $m"; exit 1; }
done
[ -u /opt/PostCall/chrome-sandbox ] && echo "NOTE | chrome-sandbox is set-uid (no user namespaces here)" || echo "NOTE | chrome-sandbox is a plain file (user namespaces work here)"
[ -e /usr/bin/postcall ] && echo "PASS | /usr/bin/postcall launcher is installed" || echo "FAIL | no /usr/bin/postcall"
[ -e /usr/share/applications/postcall.desktop ] && echo "PASS | the launcher entry is installed" || echo "FAIL | no postcall.desktop"

# 2. Tools for the check: a virtual display, ps and lsof, curl and a recent Node (the check scripts need one).
case "$PKG" in
  *.deb) apt-get install -y -qq --no-install-recommends xvfb xauth lsof procps curl xz-utils ca-certificates >/dev/null 2>&1 ;;
  *.rpm) dnf install -y -q xorg-x11-server-Xvfb xorg-x11-xauth lsof procps-ng curl xz ca-certificates >/dev/null 2>&1 ;;
esac
NODE_VERSION=24.13.0
case "$(uname -m)" in
  aarch64) node_arch=arm64; sum=aa881151bd0f9f154a0424dd60a72e9ce10672619121658c278a24327ef46831 ;;
  x86_64) node_arch=x64; sum=e798599612f4bb71333a3397ab0d095fd62214e115aea45aa858a145fc72d67e ;;
esac
f="node-v$NODE_VERSION-linux-$node_arch.tar.xz"
curl -fsSL -o "/tmp/$f" "https://nodejs.org/dist/v$NODE_VERSION/$f"
echo "$sum  /tmp/$f" | sha256sum -c - >/dev/null
tar -xJf "/tmp/$f" -C /usr/local --strip-components=1

# 3. Start the app as an ordinary user, as a person double-clicking the launcher would.
useradd -m tester 2>/dev/null || true
mkdir -p /tmp/out && chown tester /tmp/out
echo "== running $CHECK as an ordinary user"
su tester -c "cd /repo/desktop && xvfb-run -a env APP_BIN=/opt/PostCall/postcall APP_ARGS='${APP_ARGS:-}' UI_OUT=/tmp/out SCRATCH=/tmp \
  node scripts/$CHECK.mjs" 2>&1 | tee /tmp/check.log
cp /tmp/out/*.png /results/ 2>/dev/null || true
if grep -q '^FAIL' /tmp/check.log; then echo "RESULT: FAILED"; exit 1; fi
echo "RESULT: ok"
