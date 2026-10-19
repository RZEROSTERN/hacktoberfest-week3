---
paths:
  - "api/**"
---

# API rules

- Configuration only through pydantic-settings and environment variables. Bind to 127.0.0.1.
- Runs on macOS, Windows and Linux: no `os.kill`, `killpg`, `sysconf`, `getpgid` or `fork` (a test enforces it; use
  `psutil`), shut down with `server.should_exit`, start programs with `creationflags=NO_WINDOW` (`app/proc.py`), and
  build paths with `pathlib` (SQLite via `URL.create`, never an f-string URL).
- Every model output is validated with Pydantic. On invalid output retry once, then return a
  clear error.
- Every extracted fact keeps its transcript source (segment id + timestamp).
- Prompts live in `api/prompts/`, versioned, never inline. They must work with any
  compatible model, not only Gemma.
- Unit tests mock the model and the transcriber. One integration test runs the real pipeline
  on a short sample.
- Never log transcript, notes or proposal content.
- Nothing may assume a fixed port, working directory, repo-relative path, model tag or the
  default Ollama URL: the api also runs as a packaged binary.
- Notes items hold text + segment ids only. Never trust a model-written quote: look it up from
  the cited segments. Ollama calls use `format` = JSON schema, `think: false`, temperature 0.
- When the notes have no budget or deadline, the code adds those open questions itself.
- Prices are written by code from the profile; the model never sees the rates. Money in model text is a hard error.
- Edits go through `apply_edit`: no prices outside the investment section, real sources only, unsourced
  items stay assumptions. Any response header the web app must read needs listing in CORS `expose_headers`.
- Model management uses only Ollama's documented endpoints. Model names are validated, cloud models are
  refused (name and `remote_host`), and a model is only used after it passed the compatibility check.
- Every refusal is `ApiError(status, code)`, never a bare `HTTPException`: the code and its English text live in
  `ERROR_MESSAGES` (`errors.py`), values for the message go in as keyword arguments, and the web app needs
  `apiErrors.<code>` in `en.json` (a test fails if one is missing). Proposal wording for each language is in `i18n.py`.
