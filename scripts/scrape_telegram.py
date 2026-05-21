import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import insert_chunk, get_existing_source_names

load_dotenv()

model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

GROUPS = [
    {"url": "https://t.me/+Yo0iDJtkB783ZDNi", "name": "EcoTech Invest"},
    {"url": "https://t.me/+1OdGE9m0dyY5MDg6", "name": "Ribas x Codex Energy"},
    {"url": "https://t.me/+Bo8HUSfH2N1iYjIy", "name": "Varto Вітрова"},
    {"url": "https://t.me/+TEz90XB19LE3ZmUy", "name": "Sabai Пхукет"},
    {"url": "https://t.me/+4UpGnnss0twzZTVi", "name": "Standard One"},
    {"url": "https://t.me/+BKOYwPgx81M2MWEy", "name": "Aiffin"},
    {"url": "https://t.me/+O1vByCyOR8QxZTNi", "name": "Deus Robotics"},
    {"url": "https://t.me/+LdEtd-iiKo84Y2Iy", "name": "MYFREEDOM"},
]


def chunk_messages(messages, target_words=300):
    chunks = []
    current_chunk = []
    current_length = 0

    for text in messages:
        current_chunk.append(text)
        current_length += len(text.split())
        if current_length >= target_words:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_length = 0

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    return chunks


async def scrape_group(client, group):
    entity = await client.get_entity(group["url"])
    messages = []

    async for msg in client.iter_messages(entity, limit=200):
        if msg.text and len(msg.text) > 30:
            messages.append(msg.text)

    if not messages:
        print(f"  No messages found in {group['name']}")
        return 0

    chunks = chunk_messages(messages)

    for chunk in chunks:
        embedding = model.encode(chunk).tolist()
        insert_chunk(
            content=chunk,
            embedding=embedding,
            source_type="telegram",
            source_name=group["name"],
            source_url=group["url"],
        )

    print(f"  Stored {len(chunks)} chunks from {group['name']}")
    return len(chunks)


async def main():
    client = TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"]),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"]
    )
    await client.start()

    existing_groups = get_existing_source_names("telegram")

    total = 0
    for group in GROUPS:
        if group["name"] in existing_groups:
            print(f"Skipping (already scraped): {group['name']}")
            continue
        print(f"Scraping: {group['name']}")
        try:
            total += await scrape_group(client, group)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  Error: {e}")

    await client.disconnect()
    print(f"\nDone. Total new chunks: {total}")


if __name__ == "__main__":
    asyncio.run(main())
