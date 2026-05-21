import os
import sys
import json
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_instruments


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        instruments = get_instruments(active_only=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"instruments": instruments}, ensure_ascii=False).encode())
