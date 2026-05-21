import subprocess
import json
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import insert_chunk, get_existing_source_urls
from embeddings import get_embedding

load_dotenv()

CHANNEL_URL = "https://www.youtube.com/@UkrInvestClub"


def get_video_urls():
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print", "url", CHANNEL_URL],
        capture_output=True, text=True
    )
    return [url for url in result.stdout.strip().split("\n") if url]


def get_transcript(video_url):
    video_id = video_url.split("v=")[-1] if "v=" in video_url else video_url.split("/")[-1]
    subprocess.run([
        "yt-dlp", "--write-auto-sub", "--sub-lang", "uk,en",
        "--skip-download", "--sub-format", "json3",
        "-o", f"/tmp/%(id)s.%(ext)s", video_url
    ], capture_output=True)

    for lang in ["uk", "en"]:
        path = f"/tmp/{video_id}.{lang}.json3"
        try:
            with open(path) as f:
                data = json.load(f)
                text = " ".join(
                    seg.get("utf8", "")
                    for event in data.get("events", [])
                    for seg in event.get("segs", [])
                    if seg.get("utf8", "").strip()
                )
                if text.strip():
                    return text
        except FileNotFoundError:
            continue
    return None


def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk.split()) > 30:
            chunks.append(chunk)
    return chunks


def process_video(video_url):
    transcript = get_transcript(video_url)
    if not transcript:
        print(f"  No transcript found for {video_url}")
        return 0

    chunks = chunk_text(transcript)
    for chunk in chunks:
        embedding = get_embedding(chunk)
        insert_chunk(
            content=chunk,
            embedding=embedding,
            source_type="youtube",
            source_name="UkrInvestClub",
            source_url=video_url,
        )

    print(f"  Stored {len(chunks)} chunks")
    return len(chunks)


def main():
    existing_urls = get_existing_source_urls("youtube")
    video_urls = get_video_urls()
    print(f"Found {len(video_urls)} videos on channel")

    total_chunks = 0
    for url in video_urls:
        if url in existing_urls:
            print(f"Skipping (already processed): {url}")
            continue
        print(f"Processing: {url}")
        total_chunks += process_video(url)

    print(f"\nDone. Total new chunks: {total_chunks}")


if __name__ == "__main__":
    main()
