#!/bin/sh
# Installs a built Linux package into a clean container of one distribution and checks that it works.
#   sh desktop/linux/verify.sh <arch> <image> [check]
#   sh desktop/linux/verify.sh arm64 ubuntu:22.04          (.deb)
#   sh desktop/linux/verify.sh arm64 fedora:latest         (.rpm)
# <arch> is arm64 or amd64 (the latter emulated on an Apple Silicon Mac: slow, so use shell-check only).
# The container is given the capabilities Chromium's own sandbox needs, because Docker's default profile
# blocks them; the sandbox stays ON. Set APP_ARGS=--no-sandbox only if even that cannot work, and say so.
set -eu
ARCH=${1:?usage: verify.sh arm64|amd64 image [shell-check|full-flow]}
IMAGE=${2:?usage: verify.sh arm64|amd64 image [shell-check|full-flow]}
CHECK=${3:-shell-check}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PKGDIR="$ROOT/desktop/release-linux/$ARCH"
case "$IMAGE" in
  fedora*|rockylinux*|almalinux*|centos*) PKG=$(cd "$PKGDIR" && ls ./*.rpm | head -1) ;;
  *) PKG=$(cd "$PKGDIR" && ls ./*.deb | head -1) ;;
esac
PKG=${PKG#./}
RESULTS="$ROOT/desktop/release-linux/results/$ARCH-$(echo "$IMAGE" | tr ':/' '--')"
mkdir -p "$RESULTS"
docker run --rm --platform "linux/$ARCH" \
  --cap-add SYS_ADMIN --security-opt seccomp=unconfined --security-opt apparmor=unconfined \
  -e APP_ARGS="${APP_ARGS:-}" \
  -v "$PKGDIR:/pkg:ro" -v "$ROOT/desktop/scripts:/repo/desktop/scripts:ro" -v "$ROOT/web/ui-check:/repo/web/ui-check:ro" \
  -v "$ROOT/samples:/repo/samples:ro" -v "$ROOT/desktop/linux/in-container.sh:/in-container.sh:ro" \
  -v "$RESULTS:/results" \
  "$IMAGE" sh /in-container.sh "/pkg/$PKG" "$CHECK" 2>&1 | tee "$RESULTS/$CHECK.log"
