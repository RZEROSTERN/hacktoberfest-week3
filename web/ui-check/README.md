# UI check

Looks at the real screens with the installed Google Chrome (headless, over the DevTools protocol; no
installs). It fills forms, clicks, waits, checks the page text and saves screenshots to
`.dev/ui-check/` (or `UI_OUT`). Node 24 or newer.

Until the models are set up the app only shows the setup screen, so complete it once before the
other flows (the setup finishes in about a minute when the language model is already installed):

```sh
make dev-api &
curl -X POST http://127.0.0.1:8765/setup/start -H 'content-type: application/json' -d '{"model":"gemma4:e4b"}'
```

```sh
make dev-api &                       # api on 8765 (needs the whisper and Ollama setup)
cd web && npm run dev &              # web on localhost:3000
curl -F file=@../samples/interview.mp3 http://127.0.0.1:8765/calls   # note the returned id
export CALL_ID=<that id>
node ui-check/profile-flow.mjs       # profile, home, upload, call page
node ui-check/draft-flow.mjs         # real draft: progress, cancel, source links (loads the language model)
```

To check the production build, run `npm run generate` and serve `.output/public` with
`python3 ui-check/spa_server.py .output/public 3000`, then `node ui-check/static-flow.mjs`. The
fallback to `200.html` matters: `nuxt generate` writes no file for routes like `/profile`, so a
plain static server answers 404 on deep links.

Each flow prints PASS or FAIL lines and the console errors it saw.

`setup-flow.mjs` is different: it starts and stops the api itself (`ROOT` is the repository folder),
uses a fresh data folder, downloads the real speech model (about 574 MB), pulls a tiny model (about
270 MB) and loads the recommended model for its check. It needs Ollama running with `gemma4:e4b`
installed, and `npm run dev` on localhost:3000:

```sh
ROOT=$PWD node web/ui-check/setup-flow.mjs
```
