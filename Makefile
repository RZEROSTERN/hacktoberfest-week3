# Development only. The packaged app gets its ports and paths from the desktop shell.
# Config comes from .env (copy of .env.example); anything not set there gets a dev default.

-include .env

export SCOPEWISE_PORT ?= 8765
export SCOPEWISE_OLLAMA_URL ?= http://127.0.0.1:11434
export SCOPEWISE_DATA_DIR ?= $(CURDIR)/.dev/data
export SCOPEWISE_MODELS_DIR ?= $(CURDIR)/.dev/models
export SCOPEWISE_CORS_ORIGINS ?= ["http://localhost:3000","http://127.0.0.1:3000"]
export SCOPEWISE_WHISPER_CLI ?= $(CURDIR)/.dev/whisper.cpp/build/bin/whisper-cli
export SCOPEWISE_TEST_WHISPER_MODEL ?= $(CURDIR)/.dev/models/whisper.cpp/ggml-base-q5_1.bin
# Development seed for the local settings table; the app never hard-codes a model tag.
export SCOPEWISE_LLM_MODEL ?= gemma4:e4b
export NUXT_PUBLIC_API_BASE ?= http://127.0.0.1:$(SCOPEWISE_PORT)

.PHONY: help setup whisper-dev dev dev-api dev-web ollama-check test test-llm test-setup lint typecheck format

help:
	@echo "make setup        install api + web dependencies and create .env"
	@echo "make whisper-dev build whisper.cpp and download the dev Whisper models into .dev/"
	@echo "make dev          start api and web together (needs Ollama running natively)"
	@echo "make dev-api      start only the api"
	@echo "make dev-web      start only the web app"
	@echo "make ollama-check check that Ollama answers and list its local models"
	@echo "make test         run api and web tests"
	@echo "make test-llm    run the real-model test on the sample call (loads the language model)"
	@echo "make test-setup  run the real download/interruption/compatibility tests (pulls a ~270 MB model)"
	@echo "make lint         ruff + eslint"
	@echo "make typecheck    mypy + nuxt typecheck"
	@echo "make format       ruff format"

setup:
	@test -f .env || cp .env.example .env
	cd api && uv sync
	cd web && npm install

whisper-dev:
	cd spike && uv sync
	test -d .dev/whisper.cpp || git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git .dev/whisper.cpp
	spike/.venv/bin/cmake -S .dev/whisper.cpp -B .dev/whisper.cpp/build
	spike/.venv/bin/cmake --build .dev/whisper.cpp/build -j --config Release
	mkdir -p .dev/models/whisper.cpp
	sh .dev/whisper.cpp/models/download-ggml-model.sh large-v3-turbo-q5_0 .dev/models/whisper.cpp
	sh .dev/whisper.cpp/models/download-ggml-model.sh base-q5_1 .dev/models/whisper.cpp

dev: ollama-check
	$(MAKE) -j2 dev-api dev-web

dev-api:
	cd api && uv run python -m app

dev-web:
	cd web && npm run dev

ollama-check:
	@curl -fsS $(SCOPEWISE_OLLAMA_URL)/api/tags >/dev/null \
		&& echo "Ollama OK at $(SCOPEWISE_OLLAMA_URL)" \
		|| (echo "Ollama is not reachable at $(SCOPEWISE_OLLAMA_URL). Start the Ollama app (native, not Docker)." && exit 1)
	@curl -fsS $(SCOPEWISE_OLLAMA_URL)/api/tags | python3 -c "import sys, json; print('Local models:', ', '.join(m['name'] for m in json.load(sys.stdin)['models']) or 'none')"

test:
	cd api && uv run pytest
	cd web && npm test

test-llm:
	cd api && SCOPEWISE_RUN_LLM_TESTS=1 uv run pytest tests/test_integration_llm.py -s -q

test-setup:
	cd api && SCOPEWISE_RUN_SETUP_TESTS=1 uv run pytest tests/test_integration_setup.py -s -q

lint:
	cd api && uv run ruff check . && uv run ruff format --check .
	cd api && uv run ruff check ../spike && uv run ruff format --check ../spike
	cd web && npm run lint

typecheck:
	cd api && uv run mypy app tests
	cd web && npm run typecheck

format:
	cd api && uv run ruff format . ../spike
