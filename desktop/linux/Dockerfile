# syntax=docker/dockerfile:1.7
#
# Builds the experimental Linux packages (.deb and .rpm) for ONE architecture, from source, inside a
# container, so the result does not depend on this Mac. Use `make linux-packages` (or build.sh).
#
# One stage per thing the app bundles, so each can be built and checked on its own:
#   ffmpeg   a minimal, LGPL-only FFmpeg (the audio converter; macOS has its own)
#   whisper  whisper-cli, the transcription engine, CPU only
#   ollama   the official Ollama release for this architecture, checked against a pinned SHA-256
#   api      the Python service as one PyInstaller program
#   web      the generated web app (the same files for every architecture)
#   package  electron-builder: .deb and .rpm
#
# The base is Ubuntu 22.04 (glibc 2.35): programs built here run on that or anything newer. Older systems
# (for example RHEL 9, glibc 2.34) are not supported. Every download is pinned by checksum or revision.

ARG UBUNTU=ubuntu:22.04@sha256:5ec03bb3441e8b0bf3b4f9cd4629a1ae763010dc3035bb8da3ae6cf026486401
ARG NODE_IMAGE=node:24.13.0-bookworm-slim@sha256:4660b1ca8b28d6d1906fd644abe34b2ed81d15434d26d845ef0aced307cf4b6f
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21

FROM ${UV_IMAGE} AS uv

FROM ${UBUNTU} AS base
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential ca-certificates cmake curl git nasm pkg-config xz-utils zstd \
 && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------------------------------
# FFmpeg 8.1.3, built with nothing but what turning an mp3, m4a, mp4 or wav into 16 kHz mono WAV needs.
# No --enable-gpl and no external libraries, so the program is LGPL-2.1-or-later. It runs as a separate
# program (not linked into anything of ours), and its source is the pinned tarball below.
FROM base AS ffmpeg
ARG FFMPEG_VERSION=8.1.3
ARG FFMPEG_SHA256=7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3
RUN curl -fsSL -o /tmp/ffmpeg.tar.xz "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz" \
 && echo "${FFMPEG_SHA256}  /tmp/ffmpeg.tar.xz" | sha256sum -c - \
 && tar -xJf /tmp/ffmpeg.tar.xz -C /tmp
WORKDIR /tmp/ffmpeg-${FFMPEG_VERSION}
RUN ./configure \
      --disable-everything --disable-autodetect --disable-doc --disable-debug --disable-network \
      --disable-ffplay --disable-ffprobe --disable-avdevice \
      --enable-protocol=file,pipe \
      --enable-demuxer=mp3,mov,wav \
      --enable-parser=mpegaudio,aac \
      --enable-decoder=mp3,mp3float,aac,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le,pcm_u8,pcm_alaw,pcm_mulaw \
      --enable-encoder=pcm_s16le \
      --enable-muxer=wav \
      --enable-filter=abuffer,abuffersink,aresample,aformat,anull \
 && make -j"$(nproc)" ffmpeg
RUN mkdir -p /out/ffmpeg \
 && strip -o /out/ffmpeg/ffmpeg ffmpeg \
 && cp COPYING.LGPLv2.1 LICENSE.md /out/ffmpeg/ \
 && echo "FFmpeg ${FFMPEG_VERSION}, source ${FFMPEG_SHA256} (ffmpeg-${FFMPEG_VERSION}.tar.xz)" > /out/ffmpeg/BUILDINFO.txt \
 && /out/ffmpeg/ffmpeg -hide_banner -version >> /out/ffmpeg/BUILDINFO.txt
# It must not be a GPL build. -L prints the license it was built under.
RUN ! grep -q -- '--enable-gpl\|--enable-nonfree\|--enable-version3' /out/ffmpeg/BUILDINFO.txt \
 && /out/ffmpeg/ffmpeg -hide_banner -L | head -3
# Smoke test with the clips of the sample call the api tests use, through the command line the api runs.
COPY api/tests/data /fixtures
RUN set -e; for clip in clip.mp3 clip.m4a clip.mp4 clip-video.mp4 clip.wav; do \
      /out/ffmpeg/ffmpeg -nostdin -hide_banner -loglevel error -y -i "/fixtures/$clip" -map 0:a:0 \
        -ac 1 -ar 16000 -c:a pcm_s16le -f wav "/tmp/$clip.wav"; \
      size=$(stat -c %s "/tmp/$clip.wav"); \
      echo "$clip -> $size bytes"; \
      [ "$size" -gt 90000 ] && [ "$size" -lt 110000 ]; \
    done; \
    ! /out/ffmpeg/ffmpeg -nostdin -loglevel quiet -y -i /fixtures/video-only.mp4 -map 0:a:0 -f wav /tmp/none.wav

# ---------------------------------------------------------------------------------------------------
# whisper-cli, pinned to the revision the benchmarks and tests used. CPU only. No CPU-specific tuning
# beyond AVX2 on x86-64 (any x86 CPU since 2013), so it runs on more machines than the one that built it.
FROM base AS whisper
ARG TARGETARCH
ARG WHISPER_REV=0c7be696371069e0baa2515ed7aa08d5a5473aa6
RUN git init -q /src \
 && git -C /src remote add origin https://github.com/ggml-org/whisper.cpp.git \
 && git -C /src fetch -q --depth 1 origin "${WHISPER_REV}" \
 && git -C /src checkout -q FETCH_HEAD
WORKDIR /src
RUN case "${TARGETARCH}" in \
      amd64) cpu="-DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON" ;; \
      *) cpu="" ;; \
    esac \
 && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
      -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF ${cpu} \
      -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF \
      -DCMAKE_EXE_LINKER_FLAGS="-static-libstdc++ -static-libgcc" \
 && cmake --build build -j"$(nproc)" --config Release --target whisper-cli
RUN mkdir -p /out/whisper \
 && strip -o /out/whisper/whisper-cli build/bin/whisper-cli \
 && cp LICENSE /out/whisper/LICENSE \
 && /out/whisper/whisper-cli --help >/dev/null 2>&1; ldd /out/whisper/whisper-cli

# ---------------------------------------------------------------------------------------------------
# Ollama, the official standalone Linux release, untouched. Its archive is bin/ollama plus lib/ollama/
# (CPU backends for each instruction set, and the NVIDIA CUDA libraries); it finds lib/ relative to bin/.
FROM base AS ollama
ARG TARGETARCH
ARG OLLAMA_VERSION=v0.35.1
COPY desktop/linux/ollama-sha256sums.txt /tmp/sums.txt
RUN --mount=type=cache,target=/dl,id=postcall-downloads \
    set -e; f="ollama-linux-${TARGETARCH}.tar.zst"; \
    fetch() { [ -f "/dl/${OLLAMA_VERSION}-$1" ] || { curl -fL --retry 3 -o "/dl/${OLLAMA_VERSION}-$1.part" "$2" && mv "/dl/${OLLAMA_VERSION}-$1.part" "/dl/${OLLAMA_VERSION}-$1"; }; \
      cp "/dl/${OLLAMA_VERSION}-$1" "/tmp/$1"; }; \
    fetch "$f" "https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}/$f"; \
    fetch LICENSE "https://raw.githubusercontent.com/ollama/ollama/${OLLAMA_VERSION}/LICENSE"; \
    cd /tmp && grep -e " $f\$" -e " LICENSE\$" sums.txt | sha256sum -c -; \
    mkdir -p /out/ollama && zstd -dc "/tmp/$f" | tar -xf - -C /out/ollama; \
    cp /tmp/LICENSE /out/ollama/LICENSE; echo "${OLLAMA_VERSION}" > /out/ollama/VERSION; \
    rm -f "/tmp/$f"
RUN /out/ollama/bin/ollama --version; du -sh /out/ollama /out/ollama/lib/ollama/*/ | sort -h | tail -6

# ---------------------------------------------------------------------------------------------------
# The api: one PyInstaller program. Python comes from uv (a standalone build), the libraries from uv.lock.
FROM base AS api
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_PYTHON_PREFERENCE=only-managed UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src/api
COPY api/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --python 3.12 \
 && uv run --frozen pyinstaller --noconfirm --clean --distpath /out --workpath /tmp/pyinstaller postcall-api.spec
# It must start and answer, on its own, on a port it is given.
RUN POSTCALL_HOST=127.0.0.1 POSTCALL_PORT=18765 POSTCALL_DATA_DIR=/tmp/pc/data POSTCALL_MODELS_DIR=/tmp/pc/models \
    POSTCALL_OLLAMA_URL=http://127.0.0.1:1 /out/postcall-api >/tmp/api.log 2>&1 & \
    for i in $(seq 1 60); do curl -fsS http://127.0.0.1:18765/health && break; sleep 1; done; \
    curl -fsS http://127.0.0.1:18765/health || { cat /tmp/api.log; exit 1; }; \
    kill %1 2>/dev/null || true

# ---------------------------------------------------------------------------------------------------
# The generated web app. Plain files, the same for every architecture, so it always builds natively.
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
# The notices screen embeds the notices file from the repository root.
COPY THIRD_PARTY_NOTICES.md /src/
COPY web/ ./
RUN npm run generate

# ---------------------------------------------------------------------------------------------------
# electron-builder: .deb and .rpm from the pieces above.
FROM base AS package-deb
ARG TARGETARCH
# Compressing the packages is the slow part (the CUDA libraries are huge): use every core.
ENV XZ_OPT=-T0
ARG NODE_VERSION=24.13.0
ARG NODE_SHA256_AMD64=e798599612f4bb71333a3397ab0d095fd62214e115aea45aa858a145fc72d67e
ARG NODE_SHA256_ARM64=aa881151bd0f9f154a0424dd60a72e9ce10672619121658c278a24327ef46831
RUN apt-get update && apt-get install -y --no-install-recommends rpm binutils && rm -rf /var/lib/apt/lists/*
RUN set -e; \
    if [ "${TARGETARCH}" = amd64 ]; then node_arch=x64; sum="${NODE_SHA256_AMD64}"; else node_arch=arm64; sum="${NODE_SHA256_ARM64}"; fi; \
    f="node-v${NODE_VERSION}-linux-${node_arch}.tar.xz"; \
    curl -fsSL -o "/tmp/$f" "https://nodejs.org/dist/v${NODE_VERSION}/$f"; \
    echo "${sum}  /tmp/$f" | sha256sum -c -; \
    tar -xJf "/tmp/$f" -C /usr/local --strip-components=1; rm "/tmp/$f"
WORKDIR /src/desktop
COPY desktop/package.json desktop/package-lock.json ./
# npm does not run Electron's own download step here (the Makefile runs it by hand too): its licence files
# are bundled, so the files must be there.
RUN --mount=type=cache,target=/root/.cache npm ci && node node_modules/electron/install.js
COPY desktop/ ./
COPY THIRD_PARTY_NOTICES.md LICENSE /src/
COPY --from=web /src/web/.output/public /src/web/.output/public
COPY --from=api /out/postcall-api build/api/postcall-api
COPY --from=ollama /out/ollama build/ollama
COPY --from=whisper /out/whisper build/whisper
COPY --from=ffmpeg /out/ffmpeg build/ffmpeg
# One layer per package type: compressing takes about ten minutes each, so a failure in the second
# must not redo the first.
RUN --mount=type=cache,target=/root/.cache \
    npm run build && npx electron-builder --linux deb --config electron-builder.yml

FROM package-deb AS package
RUN --mount=type=cache,target=/root/.cache \
    npx electron-builder --linux rpm --config electron-builder.yml
RUN cd release && for f in *.deb *.rpm; do sha256sum "$f" > "$f.sha256"; done && ls -la

# Each piece on its own, for trying it without building everything (build.sh <arch> <stage>).
FROM scratch AS ffmpeg-out
COPY --from=ffmpeg /out /
FROM scratch AS whisper-out
COPY --from=whisper /out /
FROM scratch AS ollama-out
COPY --from=ollama /out /
FROM scratch AS api-out
COPY --from=api /out /
FROM scratch AS deb-out
COPY --from=package-deb /src/desktop/release/*.deb /

FROM scratch AS out
COPY --from=package /src/desktop/release/*.deb /src/desktop/release/*.rpm /src/desktop/release/*.sha256 /
