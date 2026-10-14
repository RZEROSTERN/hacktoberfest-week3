#!/bin/sh
# Builds one self-contained, relocatable whisper-cli for Apple Silicon into desktop/build/whisper/.
# The source is pinned to the revision the model spike and the tests used.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SRC="$ROOT/.dev/whisper.cpp"
OUT="$ROOT/desktop/build/whisper"
REV="0c7be696371069e0baa2515ed7aa08d5a5473aa6"

if [ ! -d "$SRC/.git" ]; then
  git init -q "$SRC"
  git -C "$SRC" remote add origin https://github.com/ggml-org/whisper.cpp.git
fi
if [ "$(git -C "$SRC" rev-parse HEAD 2>/dev/null || true)" != "$REV" ]; then
  git -C "$SRC" fetch -q --depth 1 origin "$REV"
  git -C "$SRC" checkout -q FETCH_HEAD
fi

CMAKE=$(command -v cmake || true)
[ -n "$CMAKE" ] || CMAKE="$ROOT/spike/.venv/bin/cmake"   # `make whisper-dev` installs it there

# Static libraries (nothing to find at run time), the Metal shaders embedded in the binary, and no
# CPU-specific tuning so it also runs on older Apple Silicon chips than the one it was built on.
"$CMAKE" -S "$SRC" -B "$SRC/build-static" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
  -DGGML_NATIVE=OFF -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON \
  -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=13.0 \
  -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF
"$CMAKE" --build "$SRC/build-static" -j --config Release --target whisper-cli

mkdir -p "$OUT"
cp "$SRC/build-static/bin/whisper-cli" "$OUT/whisper-cli"
cp "$SRC/LICENSE" "$OUT/LICENSE"
echo "built $OUT/whisper-cli ($(du -h "$OUT/whisper-cli" | cut -f1))"
