---
paths:
  - "api/**"
---

# API rules

- Configuration only through pydantic-settings and environment variables. Bind to 127.0.0.1.
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
