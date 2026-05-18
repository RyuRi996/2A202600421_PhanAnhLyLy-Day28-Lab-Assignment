# smoke-tests/test_e2e.py
import pytest
import requests
import time
import os

BASE_URL = "http://localhost:8000"
VLLM_URL = os.environ.get("VLLM_NGROK_URL", "")


# ── Test 1: Happy Path — Full Inference Request ───────────────
class TestHappyPath:
    def test_full_inference_returns_200(self):
        """API Gateway returns 200 with answer field (LLM may be fallback)"""
        resp = requests.post(f"{BASE_URL}/api/v1/chat", json={
            "query": "What is platform engineering?",
            "embedding": [0.1] * 384
        }, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 10
        assert "latency_ms" in data

    def test_health_check_passes(self):
        """API Gateway health check"""
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── Test 2: Data Ingestion Journey ───────────────────────────
class TestDataIngestion:
    def test_kafka_ingest_and_qdrant_store(self):
        """Qdrant vector store has documents loaded"""
        # Check Qdrant collection exists and has data
        resp = requests.get("http://localhost:6333/collections/documents", timeout=5)
        assert resp.status_code == 200
        count = resp.json()["result"]["points_count"]
        assert count > 0, (
            f"Qdrant has {count} points. Run: python scripts/05_embed_to_qdrant.py"
        )
        print(f"Vector store has {count} documents")


# ── Test 3: Observability Journey ────────────────────────────
class TestObservability:
    def test_prometheus_scrapes_api_gateway(self):
        """Prometheus is up and has api-gateway target"""
        resp = requests.get("http://localhost:9090/api/v1/query",
                            params={"query": "up{job='api-gateway'}"}, timeout=5)
        assert resp.status_code == 200
        result = resp.json()["data"]["result"]
        assert len(result) > 0, "No 'api-gateway' target in Prometheus"

    def test_grafana_dashboard_accessible(self):
        """Grafana dashboard is accessible"""
        resp = requests.get("http://localhost:3000/api/health",
                            auth=("admin", "admin"), timeout=5)
        assert resp.status_code == 200


# ── Test 4: Error Handling & Failure Path ────────────────────
class TestFailurePath:
    def test_invalid_request_returns_422(self):
        """API Gateway rejects request with missing required field"""
        resp = requests.post(f"{BASE_URL}/api/v1/chat", json={})
        assert resp.status_code in [400, 422]

    def test_timeout_handled_gracefully(self):
        """Service remains healthy after client timeout"""
        try:
            requests.post(f"{BASE_URL}/api/v1/chat",
                          json={"query": "test", "embedding": [0.1] * 384},
                          timeout=0.001)
        except requests.exceptions.Timeout:
            pass  # Expected

        health = requests.get(f"{BASE_URL}/health", timeout=5)
        assert health.status_code == 200


# ── Test 5: Feature Store Journey ────────────────────────────
class TestFeatureStore:
    def test_feast_redis_has_features(self):
        """Redis feature store has feature entries"""
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True, socket_timeout=5)
        keys = r.keys("feature:*")
        assert len(keys) > 0, (
            "No features in Redis. Run: python scripts/03_delta_to_feast.py"
        )
        print(f"Feature store has {len(keys)} feature entries")
