import os
import sys
import json
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import save_profile


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length))
        user_id = body.get("user_id")
        profile_data = body.get("profile")

        if not user_id:
            self._respond(400, {"error": "user_id is required"})
            return
        if not profile_data:
            self._respond(400, {"error": "profile data is required"})
            return

        save_profile(user_id, profile_data)
        self._respond(200, {"status": "ok"})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
