# Third-party notices

Scopewise is built from open-source parts and runs them entirely on your computer. This page lists what is inside the app or downloaded by it, and under which license. The full license texts of the language engine, the transcription engine and the desktop shell are shipped in the app (inside the `ollama`, `whisper` and `electron` folders of its resources).

## Language engine: Ollama (MIT)

Version 0.35.1, bundled inside the app. Copyright (c) Ollama. Licensed under the MIT License. https://github.com/ollama/ollama

Ollama includes these components, whose license files ship with it: llama.cpp (MIT), MLX and MLX-C (MIT), fmt (MIT), cpp-httplib (MIT), picojson (BSD-2-Clause), DLPack (Apache 2.0), XGrammar (Apache 2.0) and the Go libraries Ollama is built from, under their own open-source licenses collected in the file GO_LICENSE.

## Transcription engine: whisper.cpp (MIT)

Built from revision 0c7be69 and bundled inside the app. Copyright (c) 2023-2026 The ggml authors. Licensed under the MIT License. https://github.com/ggml-org/whisper.cpp

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

The Python runtime is under the PSF License. The libraries inside it:

- FastAPI, Pydantic, pydantic-settings, SQLModel, SQLAlchemy, h11, anyio, httptools, uvloop, watchfiles, PyYAML, charset-normalizer: MIT License.
- Starlette, Uvicorn, HTTPX, HTTPCore, Click, websockets, python-dotenv, idna: BSD-3-Clause License.
- python-multipart: Apache License 2.0.
- ReportLab (PDF export): BSD License. https://www.reportlab.com
- Pillow: MIT-CMU License.
- certifi: Mozilla Public License 2.0.

## Interface: Nuxt and Vue (MIT)

The screens are built with Nuxt, Vue and Vue Router, all licensed under the MIT License. https://nuxt.com

## Provided by your Mac

Audio recordings are converted with afconvert, a tool that is part of macOS. It is not distributed with Scopewise.
