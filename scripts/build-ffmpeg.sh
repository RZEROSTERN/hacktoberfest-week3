#!/usr/bin/env bash
# Builds a minimal, LGPL-only FFmpeg from the pinned source: just enough to turn an mp3, m4a, mp4 or wav into the
# 16 kHz mono WAV that whisper.cpp reads. macOS does not need it (it has afconvert).
#
#   build-ffmpeg.sh <output folder>
#
# Run directly on Linux, or inside MSYS2's UCRT64 shell on Windows (build-ffmpeg.mjs does that). Reads FFMPEG_VERSION,
# FFMPEG_URL and FFMPEG_SHA256 from the environment, and FIXTURES (a folder with the api's test clips) for the check.
# No --enable-gpl, no --enable-nonfree and no external libraries: the program is LGPL-2.1-or-later, runs as a
# separate program and is not linked into anything of ours.
set -euo pipefail

OUT=${1:?usage: build-ffmpeg.sh <output folder>}
: "${FFMPEG_VERSION:?}" "${FFMPEG_URL:?}" "${FFMPEG_SHA256:?}"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) EXE=.exe; WINDOWS=1; EXTRA_LD="-static" ;;   # no MinGW runtime DLLs to ship
  *) EXE=""; WINDOWS=""; EXTRA_LD="" ;;
esac

curl -fsSL --retry 3 -o "$WORK/ffmpeg.tar.xz" "$FFMPEG_URL"
echo "$FFMPEG_SHA256  $WORK/ffmpeg.tar.xz" | sha256sum -c -
tar -xJf "$WORK/ffmpeg.tar.xz" -C "$WORK"
cd "$WORK/ffmpeg-$FFMPEG_VERSION"

echo "compiler: $(command -v gcc || echo none)"; gcc --version | head -1 || true
if ! ./configure \
  --disable-everything --disable-autodetect --disable-doc --disable-debug --disable-network \
  --disable-ffplay --disable-ffprobe --disable-avdevice \
  --enable-protocol=file,pipe \
  --enable-demuxer=mp3,mov,wav \
  --enable-parser=mpegaudio,aac \
  --enable-decoder=mp3,mp3float,aac,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le,pcm_u8,pcm_alaw,pcm_mulaw \
  --enable-encoder=pcm_s16le \
  --enable-muxer=wav \
  ${EXTRA_LD:+--extra-ldflags="$EXTRA_LD"} \
  --enable-filter=abuffer,abuffersink,aresample,aformat,anull; then
  echo "---- configure failed; the end of ffbuild/config.log:" >&2
  tail -n 60 ffbuild/config.log >&2 || true
  exit 1
fi
make -j"$(nproc)" "ffmpeg$EXE"

mkdir -p "$OUT"
strip -o "$OUT/ffmpeg$EXE" "ffmpeg$EXE"
cp COPYING.LGPLv2.1 LICENSE.md "$OUT/"
{ echo "FFmpeg $FFMPEG_VERSION, source $FFMPEG_SHA256 ($(basename "$FFMPEG_URL"))"; "$OUT/ffmpeg$EXE" -hide_banner -version; } > "$OUT/BUILDINFO.txt"

# On Windows it must need nothing but the system's own DLLs: the MinGW runtimes would not be on the user's computer.
if [ -n "$WINDOWS" ]; then
  objdump -p "$OUT/ffmpeg$EXE" | grep "DLL Name" | sed 's/^[[:space:]]*//' | tee -a "$OUT/BUILDINFO.txt"
  if objdump -p "$OUT/ffmpeg$EXE" | grep -qiE 'DLL Name: (libwinpthread|libgcc|libstdc|libssp)'; then
    echo "ffmpeg.exe depends on a MinGW runtime DLL that Windows does not have" >&2; exit 1
  fi
fi

# It must not be a GPL build.
if grep -q -e '--enable-gpl' -e '--enable-nonfree' -e '--enable-version3' "$OUT/BUILDINFO.txt"; then
  echo "this FFmpeg is not LGPL-only" >&2; exit 1
fi

# And it must do the one job: every kind of clip, through the command line the api runs.
if [ -n "${FIXTURES:-}" ]; then
  for clip in clip.mp3 clip.m4a clip.mp4 clip.wav; do
    "$OUT/ffmpeg$EXE" -nostdin -hide_banner -loglevel error -y -i "$FIXTURES/$clip" -map 0:a:0 \
      -ac 1 -ar 16000 -c:a pcm_s16le -f wav "$WORK/$clip.wav"
    size=$(wc -c < "$WORK/$clip.wav")
    echo "$clip -> $size bytes"
    [ "$size" -gt 90000 ] && [ "$size" -lt 110000 ]
  done
fi
echo "FFmpeg $FFMPEG_VERSION built in $OUT"
