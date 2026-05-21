import os
import sys
import json
from http.server import BaseHTTPRequestHandler
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import match_chunks
from llm_provider import get_provider, SYSTEM_PROMPT

model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length))
        question = body.get("question", "")

        if not question:
            self._respond(400, {"error": "question is required"})
            return

        query_embedding = model.encode(question).tolist()
        chunks = match_chunks(query_embedding, match_count=5, match_threshold=0.7)

        context = "\n\n---\n\n".join(r["content"] for r in chunks)

        provider = get_provider()

        if context:
            user_message = f"Контекст:\n{context}\n\nПитання: {question}"
        else:
            user_message = f"Контексту не знайдено. Питання: {question}"

        answer = provider.synthesize(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message
        )

        self._respond(200, {
            "answer": answer,
            "sources": [
                {"name": r["source_name"], "type": r["source_type"]}
                for r in chunks
            ]
        })

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
