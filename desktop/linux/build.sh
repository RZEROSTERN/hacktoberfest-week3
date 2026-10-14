#!/bin/sh
# Builds the Linux packages for one architecture, in a container, into desktop/release-linux/<arch>/.
#   sh desktop/linux/build.sh arm64      (native on an Apple Silicon Mac)
#   sh desktop/linux/build.sh amd64      (x86-64: emulated on an Apple Silicon Mac, so much slower)
# A second argument builds just one piece (ffmpeg, whisper, ollama, api, deb) and writes what it
# produced to desktop/release-linux/<arch>-<stage>/, which is how each piece is tried on its own.
set -eu
ARCH=${1:?usage: build.sh arm64|amd64 [stage]}
case "$ARCH" in arm64|amd64) ;; *) echo "architecture must be arm64 or amd64" >&2; exit 2 ;; esac
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
STAGE=${2:-out}
case "$STAGE" in out|ffmpeg|whisper|ollama|api|deb) ;; *) echo "stage must be ffmpeg, whisper, ollama, api or deb" >&2; exit 2 ;; esac
DEST="$ROOT/desktop/release-linux/$ARCH"
if [ "$STAGE" != out ]; then DEST="$DEST-$STAGE"; STAGE="$STAGE-out"; fi
rm -rf "$DEST"
docker buildx build --platform "linux/$ARCH" -f "$ROOT/desktop/linux/Dockerfile" \
  --target "$STAGE" --output "type=local,dest=$DEST" "$ROOT"
echo "built into $DEST"; ls -la "$DEST"
