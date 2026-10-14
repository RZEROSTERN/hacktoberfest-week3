"""A local HTTP server for download tests: supports Range and can drop the connection mid-file."""

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class RangeServer:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.requests: list[str | None] = []  # the Range header of each request
        self.drop_after: int | None = (
            None  # send this many bytes of the next response, then hang up
        )
        self.ignore_range = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner.requests.append(self.headers.get("Range"))
                body = owner.data
                start, status = 0, 200
                header = self.headers.get("Range")
                if header and not owner.ignore_range:
                    start = int(header.removeprefix("bytes=").split("-")[0])
                    if start >= len(body):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{len(body)}")
                        self.end_headers()
                        return
                    status = 206
                self.send_response(status)
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
                self.send_header("Content-Length", str(len(body) - start))
                self.end_headers()
                chunk = body[start:]
                if owner.drop_after is not None:
                    chunk, owner.drop_after = chunk[: owner.drop_after], None
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    self.close_connection = True
                    self.connection.close()  # abrupt: fewer bytes than Content-Length
                    return
                self.wfile.write(chunk)

            def log_message(self, *args: Any) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/model.bin"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "RangeServer":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()
