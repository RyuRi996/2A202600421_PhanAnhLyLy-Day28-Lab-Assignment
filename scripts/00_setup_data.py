#!/usr/bin/env python3
"""
Setup script: pre-populate Qdrant and Redis so smoke tests pass.
Run after docker compose up -d and services are healthy.
"""
import sys
import time
import json
import math
import requests
import redis

QDRANT_URL = "http://localhost:6333"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

SAMPLE_DOCS = [
    {"id": "doc_001", "text": "AI platform integration test"},
    {"id": "doc_002", "text": "Kafka to Delta Lake pipeline"},
    {"id": "doc_003", "text": "Event-driven architecture with Kafka"},
    {"id": "doc_004", "text": "Vector search with Qdrant vector database"},
    {"id": "doc_005", "text": "Feature store with Feast and Redis"},
]


def wait_for_service(url: str, name: str, retries: int = 30):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=3)
            if r.status_code < 500:
                print(f"  {name} ready")
                return True
        except Exception:
            pass
        print(f"  Waiting for {name}... ({i+1}/{retries})")
        time.sleep(2)
    return False


def local_embed(texts: list[str], dim: int = 384) -> list[list[float]]:
    embeddings = []
    for text in texts:
        vec = [0.0] * dim
        for i, ch in enumerate(text):
            vec[i % dim] += ord(ch) / 1000.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        embeddings.append([x / norm for x in vec])
    return embeddings


def setup_qdrant():
    print("\n[Qdrant] Creating 'documents' collection...")
    # Delete if exists
    requests.delete(f"{QDRANT_URL}/collections/documents", timeout=5)

    resp = requests.put(f"{QDRANT_URL}/collections/documents", json={
        "vectors": {"size": 384, "distance": "Cosine"}
    }, timeout=10)
    resp.raise_for_status()

    texts = [d["text"] for d in SAMPLE_DOCS]
    embeddings = local_embed(texts)

    points = [
        {"id": i, "vector": emb, "payload": doc}
        for i, (emb, doc) in enumerate(zip(embeddings, SAMPLE_DOCS))
    ]
    resp = requests.put(f"{QDRANT_URL}/collections/documents/points", json={
        "points": points
    }, timeout=10)
    resp.raise_for_status()
    print(f"  Inserted {len(points)} vectors into Qdrant")


def setup_redis():
    print("\n[Redis] Populating feature store...")
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_timeout=5)
    r.ping()
    for doc in SAMPLE_DOCS:
        key = f"feature:{doc['id']}"
        r.set(key, json.dumps({
            "text": doc["text"],
            "timestamp": time.time(),
            "processed": True
        }))
    print(f"  Stored {len(SAMPLE_DOCS)} features in Redis")


def main():
    print("=== Setup: waiting for services ===")
    ok_qdrant = wait_for_service(f"{QDRANT_URL}/healthz", "Qdrant")
    ok_api = wait_for_service("http://localhost:8000/health", "API Gateway")

    if not ok_qdrant:
        print("ERROR: Qdrant not available. Is docker compose running?")
        sys.exit(1)

    try:
        setup_qdrant()
        setup_redis()
        print("\n=== Setup complete. Ready to run smoke tests. ===")
    except Exception as e:
        print(f"ERROR during setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
