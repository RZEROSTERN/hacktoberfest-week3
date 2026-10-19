# Third-party notices

PostCall is built from open-source parts and runs them entirely on your computer. This page lists what is inside the app or downloaded by it, and under which license. The full license texts of the language engine, the transcription engine, the desktop shell and (on Windows and Linux) the audio converter are shipped in the app (inside the `ollama`, `whisper`, `electron` and `ffmpeg` folders of its resources).

## Language engine: Ollama (MIT)

Version 0.35.1, bundled inside the app. Copyright (c) Ollama. Licensed under the MIT License. https://github.com/ollama/ollama

On Windows and Linux the app carries Ollama's official release without its NVIDIA CUDA and AMD ROCm libraries: the CPU backends and the Vulkan backend, which can use an AMD, Intel or NVIDIA graphics card through its Vulkan driver. The Windows build also includes the LLVM C++ and OpenMP runtimes (Apache License 2.0 with LLVM exceptions) and the MinGW-w64 winpthreads library, and its Vulkan folder carries Microsoft's Visual C++ runtime libraries, which Microsoft allows applications to redistribute.

Ollama includes these components, whose license files ship with it: llama.cpp (MIT), MLX and MLX-C (MIT), fmt (MIT), cpp-httplib (MIT), picojson (BSD-2-Clause), DLPack (Apache 2.0), XGrammar (Apache 2.0) and the Go libraries Ollama is built from, under their own open-source licenses collected in the file GO_LICENSE.

## Transcription engine: whisper.cpp (MIT)

Built from revision 0c7be69 and bundled inside the app (Metal on macOS, CPU only on Windows and Linux). Copyright (c) 2023-2026 The ggml authors. Licensed under the MIT License. https://github.com/ggml-org/whisper.cpp

## Speech model: Whisper (MIT)

Whisper large-v3-turbo, quantized (q5_0) by the whisper.cpp project. The original Whisper model is copyright (c) OpenAI and licensed under the MIT License. It is not inside the app: it is downloaded once from Hugging Face (ggerganov/whisper.cpp) when you approve it, and checked against a fixed checksum. https://github.com/openai/whisper

## Language models (downloaded on request)

No language model is inside the app. You choose one on the first-launch screen or in Settings, and Ollama downloads it from the Ollama library. The models we tested and list are:

- Gemma 4 (E4B and 12B), by Google. Apache License 2.0. The recommended model is Gemma 4 E4B.
- Qwen 3.5 (4B and 9B), by Alibaba Cloud. Apache License 2.0.
- Mistral Nemo 12B, by Mistral AI and NVIDIA. Apache License 2.0.

If you type another model name under "Advanced", its license is the one published with that model in the Ollama library. https://ollama.com/library

## Desktop shell: Electron (MIT)

Electron is copyright (c) Electron contributors and licensed under the MIT License. It includes Chromium and its own third-party components, each under its own open-source license; their texts are in the file LICENSES.chromium.html in the `electron` folder of the app's resources. https://www.electronjs.org

## Local service: Python and its libraries

The service that runs next to the window is written in Python and packed into one program with PyInstaller. PyInstaller is licensed under GPL-2.0-or-later with an exception that allows the programs it builds to be distributed under any license. https://pyinstaller.org

The Python runtime is under the PSF License. On Windows and Linux it comes from the python-build-standalone project and carries the libraries CPython itself needs (OpenSSL, SQLite, zlib, xz, libffi and others), each under its own open-source license. The libraries inside it:

- FastAPI, Pydantic, pydantic-settings, SQLModel, SQLAlchemy, h11, anyio, httptools, uvloop, watchfiles, PyYAML, charset-normalizer: MIT License.
- Starlette, Uvicorn, HTTPX, HTTPCore, Click, websockets, python-dotenv, idna: BSD-3-Clause License.
- python-multipart: Apache License 2.0.
- ReportLab (PDF export): BSD License. https://www.reportlab.com
- psutil: BSD-3-Clause License.
- Pillow: MIT-CMU License.
- certifi: Mozilla Public License 2.0.

## Interface: Nuxt and Vue (MIT)

The screens are built with Nuxt, Vue, Vue Router and Vue I18n (which translates them), all licensed under the MIT License. https://nuxt.com

## Audio converter

On macOS, audio recordings are converted with afconvert, a tool that is part of macOS. It is not distributed with PostCall.

On Windows and Linux, recordings are converted with FFmpeg 8.1.3, which is included. FFmpeg is licensed under the GNU Lesser General Public License, version 2.1 or later (the license text is in the `ffmpeg` folder of the app's resources). It is built from source with only what reading mp3, m4a, mp4 and wav files needs, and without any GPL-licensed part, and PostCall runs it as a separate program. The exact source is the file ffmpeg-8.1.3.tar.xz from https://ffmpeg.org/releases/ (SHA-256 7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3); the build options are listed in the file BUILDINFO.txt in the same folder and the build recipe is `scripts/build-ffmpeg.sh` in the PostCall repository (https://github.com/RZEROSTERN/hacktoberfest-week3). You can build the same program from those, or ask for the source through the repository's issues. https://ffmpeg.org

## Provided by your computer

PostCall does not distribute the parts of your operating system it uses: on macOS the system frameworks and afconvert; on Windows the system DLLs; on Linux the C library, GTK and the other system libraries your distribution provides.
