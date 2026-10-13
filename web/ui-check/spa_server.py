"""Static server with an SPA fallback, like the desktop shell will need (`nuxt generate` with ssr false
only writes index.html, 200.html and 404.html)."""
import http.server, os, sys
root, port = sys.argv[1], int(sys.argv[2])
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=root, **k)
    def send_head(self):
        path = self.translate_path(self.path.split("?")[0])
        if not os.path.exists(path) and not os.path.splitext(path)[1]:
            self.path = "/200.html"
        return super().send_head()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
