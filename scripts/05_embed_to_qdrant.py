# scripts/05_embed_to_qdrant.py
import os
import math
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

EMBED_URL = os.environ.get("EMBED_NGROK_URL", "")
qdrant = QdrantClient(host="localhost", port=6333)


def local_embed(texts: list[str]) -> list[list[float]]:
    """Simple deterministic local embeddings when Kaggle not available."""
    dim = 384
    embeddings = []
    for text in texts:
        vec = [0.0] * dim
        for i, ch in enumerate(text[:dim]):
            vec[i % dim] += ord(ch) / 1000.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        embeddings.append([x / norm for x in vec])
    return embeddings


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if EMBED_URL and "placeholder" not in EMBED_URL:
        try:
            resp = requests.post(f"{EMBED_URL}/embed", json={"texts": texts}, timeout=10)
            resp.raise_for_status()
            return resp.json()["embeddings"]
        except Exception as e:
            print(f"Remote embedding failed ({e}), falling back to local embeddings")
    return local_embed(texts)


def embed_and_store(records: list[dict]):
    # Create/recreate collection
    existing = [c.name for c in qdrant.get_collections().collections]
    if "documents" in existing:
        qdrant.delete_collection("documents")
    qdrant.create_collection(
        collection_name="documents",
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )

    texts = [r["text"] for r in records]
    embeddings = get_embeddings(texts)

    points = [
        PointStruct(id=i, vector=emb, payload=rec)
        for i, (emb, rec) in enumerate(zip(embeddings, records))
    ]
    qdrant.upsert(collection_name="documents", points=points)
    print(f"Integration 5 OK: {len(points)} vectors stored in Qdrant")


if __name__ == "__main__":
    embed_and_store([
        {"id": "doc_001", "text": "AI platform integration test"},
        {"id": "doc_002", "text": "Kafka to Airflow pipeline"},
        {"id": "doc_003", "text": "Event-driven architecture with Kafka"},
        {"id": "doc_004", "text": "Vector search with Qdrant"},
        {"id": "doc_005", "text": "Feature store with Feast and Redis"},
    ])
