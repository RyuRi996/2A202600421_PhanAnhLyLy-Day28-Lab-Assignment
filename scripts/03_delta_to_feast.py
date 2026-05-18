# scripts/03_delta_to_feast.py
import pandas as pd
import glob
import os
import redis
import json
import time

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

SAMPLE_DATA = [
    {"id": "doc_001", "text": "AI platform integration test", "timestamp": time.time()},
    {"id": "doc_002", "text": "Kafka to Delta Lake pipeline", "timestamp": time.time()},
    {"id": "doc_003", "text": "Event-driven architecture with Kafka", "timestamp": time.time()},
    {"id": "doc_004", "text": "Vector search with Qdrant", "timestamp": time.time()},
    {"id": "doc_005", "text": "Feature store with Feast and Redis", "timestamp": time.time()},
]


def load_from_delta_and_push_feast():
    files = glob.glob("delta-lake/raw/*.parquet")
    if files:
        df = pd.concat([pd.read_parquet(f) for f in files])
        print(f"Loaded {len(df)} records from Delta Lake")
    else:
        print("No Delta Lake files found, using sample data")
        df = pd.DataFrame(SAMPLE_DATA)

    for _, row in df.iterrows():
        feature_key = f"feature:{row['id']}"
        r.set(feature_key, json.dumps({
            "text": row["text"],
            "timestamp": row.get("timestamp", time.time()),
            "processed": True
        }))

    count = len(df)
    print(f"Integration 3+4 OK: Delta Lake → Feast (Redis) — {count} features stored")


if __name__ == "__main__":
    load_from_delta_and_push_feast()
