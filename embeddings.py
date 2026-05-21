import os
import httpx
import numpy as np
from dotenv import load_dotenv

load_dotenv()

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
HF_API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{EMBED_MODEL}"
HF_TOKEN = os.environ.get("HF_TOKEN", "")


def get_embedding(text: str) -> list[float]:
    headers = {}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    response = httpx.post(
        HF_API_URL,
        headers=headers,
        json={"inputs": text, "options": {"wait_for_model": True}},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    headers = {}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    response = httpx.post(
        HF_API_URL,
        headers=headers,
        json={"inputs": texts, "options": {"wait_for_model": True}},
        timeout=60
    )
    response.raise_for_status()
    return response.json()
