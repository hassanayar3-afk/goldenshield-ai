"""GoldenShield Terminal HTTP handler."""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler

from terminal_app.http.json_io import send_cors
from terminal_app.routes.router import handle_get, handle_post, handle_put


class GoldenShieldRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        send_cors(self)
        self.end_headers()

    def do_GET(self) -> None:
        handle_get(self)

    def do_POST(self) -> None:
        handle_post(self)

    def do_PUT(self) -> None:
        handle_put(self)
