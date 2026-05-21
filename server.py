"""
Local dev server for testing the API.
Run: python server.py
Then test: curl -X POST http://localhost:8000/api/ask -H "Content-Type: application/json" -d '{"question": "що таке ОВДП?"}'
"""
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))
from db import match_chunks, get_instruments, get_profile, save_profile, init_db
from llm_provider import get_provider, SYSTEM_PROMPT, SUGGESTION_PROMPT
from dotenv import load_dotenv

load_dotenv()

from embeddings import get_embedding


class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/instruments":
            instruments = get_instruments(active_only=True)
            self._respond(200, {"instruments": instruments})

        elif path == "/api/health":
            from db import get_db
            conn = get_db()
            chunks_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            instruments_count = conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
            conn.close()
            self._respond(200, {
                "status": "ok",
                "chunks": chunks_count,
                "instruments": instruments_count
            })
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        if path == "/api/ask":
            self._handle_ask(body)
        elif path == "/api/suggest":
            self._handle_suggest(body)
        elif path == "/api/profile":
            self._handle_profile(body)
        else:
            self._respond(404, {"error": "not found"})

    def _handle_ask(self, body):
        question = body.get("question", "")
        if not question:
            self._respond(400, {"error": "question is required"})
            return

        query_embedding = get_embedding(question)
        chunks = match_chunks(query_embedding, match_count=5, match_threshold=0.7)
        context = "\n\n---\n\n".join(r["content"] for r in chunks)

        provider = get_provider()
        if context:
            user_message = f"Контекст:\n{context}\n\nПитання: {question}"
        else:
            user_message = f"Контексту не знайдено. Питання: {question}"

        answer = provider.synthesize(system_prompt=SYSTEM_PROMPT, user_message=user_message)

        self._respond(200, {
            "answer": answer,
            "sources": [{"name": r["source_name"], "type": r["source_type"]} for r in chunks]
        })

    def _handle_suggest(self, body):
        user_id = body.get("user_id")
        if not user_id:
            self._respond(400, {"error": "user_id is required"})
            return

        profile = get_profile(user_id)
        if not profile:
            self._respond(400, {"error": "Profile not found"})
            return

        instruments = get_instruments(
            active_only=True,
            max_risk=profile["risk_tolerance"],
            max_amount=profile["available_amount"]
        )

        self._respond(200, {"suggestions": instruments})

    def _handle_profile(self, body):
        user_id = body.get("user_id")
        profile_data = body.get("profile")
        if not user_id or not profile_data:
            self._respond(400, {"error": "user_id and profile required"})
            return

        save_profile(user_id, profile_data)
        self._respond(200, {"status": "ok"})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    def log_message(self, format, *args):
        print(f"[API] {args[0]}")


def main():
    init_db()
    port = int(os.environ.get("API_PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    print(f"API server running on http://localhost:{port}")
    print(f"  Health check: GET  /api/health")
    print(f"  Ask question: POST /api/ask")
    print(f"  Instruments:  GET  /api/instruments")
    print(f"  Suggest:      POST /api/suggest")
    print(f"  Profile:      POST /api/profile")
    server.serve_forever()


if __name__ == "__main__":
    main()
