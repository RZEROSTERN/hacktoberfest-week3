# UI check

Looks at the real screens with the installed Google Chrome (headless, over the DevTools protocol; no
installs). It fills forms, clicks, waits, checks the page text and saves screenshots to
`.dev/ui-check/` (or `UI_OUT`). Node 24 or newer.

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
