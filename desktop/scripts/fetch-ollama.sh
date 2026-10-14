#!/bin/sh
# Downloads the official standalone Ollama for macOS into desktop/build/ollama/, checks its SHA-256 (the
# digest GitHub publishes for the release asset) and keeps only what Apple Silicon loads:
# `ollama`, its `llama-server` runner, the Metal libraries, and every license file. The Intel
# libraries, the Intel CPU backends and the quantize tool are never used by this app.
# The binaries are Ollama's own and stay untouched, so their signature stays valid.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
VERSION="v0.35.1"   # the version every test in this repository ran against
SHA256="3137dbf28948ee844e0fb3e584d9b5de6879d73d9f0cb7eff3ad64930601d307"
# The archive carries the licenses of Ollama's parts but not Ollama's own, so that one comes from the
# same tag of the repository, also pinned by checksum.
LICENSE_SHA256="5934ed2ce0d15154bcdb9c85203210abac0da4314af34081e36df4599f90b226"
CACHE="$ROOT/.dev/downloads"
OUT="$ROOT/desktop/build/ollama"
TGZ="$CACHE/ollama-darwin-$VERSION.tgz"
LICENSE_FILE="$CACHE/ollama-LICENSE-$VERSION"

mkdir -p "$CACHE"
if [ ! -f "$TGZ" ]; then
  curl -fL --retry 3 -o "$TGZ.part" "https://github.com/ollama/ollama/releases/download/$VERSION/ollama-darwin.tgz"
  mv "$TGZ.part" "$TGZ"
fi
echo "$SHA256  $TGZ" | shasum -a 256 -c - >/dev/null || { echo "checksum mismatch for $TGZ" >&2; rm -f "$TGZ"; exit 1; }

if [ ! -f "$LICENSE_FILE" ]; then
  curl -fL --retry 3 -o "$LICENSE_FILE" "https://raw.githubusercontent.com/ollama/ollama/$VERSION/LICENSE"
fi
echo "$LICENSE_SHA256  $LICENSE_FILE" | shasum -a 256 -c - >/dev/null || { echo "checksum mismatch for $LICENSE_FILE" >&2; rm -f "$LICENSE_FILE"; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
tar -xzf "$TGZ" -C "$WORK"
rm -rf "$OUT"
mkdir -p "$OUT"
cp "$WORK/ollama" "$WORK/llama-server" "$OUT/"
cp -R "$WORK/mlx_metal_v3" "$WORK/mlx_metal_v4" "$OUT/"
for f in "$WORK"/*LICENSE* "$WORK"/*NOTICE*; do cp "$f" "$OUT/"; done
cp "$LICENSE_FILE" "$OUT/LICENSE"
echo "$VERSION" > "$OUT/VERSION"
echo "Ollama $VERSION ready in $OUT ($(du -sh "$OUT" | cut -f1))"
