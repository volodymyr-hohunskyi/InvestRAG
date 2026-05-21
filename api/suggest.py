import os
import sys
import json
from http.server import BaseHTTPRequestHandler
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_profile, get_instruments, match_chunks
from llm_provider import get_provider, SUGGESTION_PROMPT

model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length))
        user_id = body.get("user_id")

        if not user_id:
            self._respond(400, {"error": "user_id is required"})
            return

        profile = get_profile(user_id)
        if not profile:
            self._respond(400, {"error": "Profile not found. Complete assessment first."})
            return

        instruments = get_instruments(
            active_only=True,
            max_risk=profile["risk_tolerance"],
            max_amount=profile["available_amount"]
        )

        goals = json.loads(profile.get("goals", "[]")) if isinstance(profile.get("goals"), str) else profile.get("goals", [])
        query = f"інвестиції {' '.join(goals)}"
        query_embedding = model.encode(query).tolist()
        chunks = match_chunks(query_embedding, match_count=3, match_threshold=0.6)
        context = "\n\n".join(r["content"] for r in chunks)

        provider = get_provider()
        prompt = SUGGESTION_PROMPT.format(
            profile=json.dumps(profile, ensure_ascii=False, default=str),
            instruments=json.dumps(instruments, ensure_ascii=False, default=str),
            context=context or "Немає додаткового контексту."
        )

        answer = provider.synthesize(
            system_prompt="Ти — інвестиційний інформаційний помічник.",
            user_message=prompt
        )

        self._respond(200, {"suggestions": answer})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
