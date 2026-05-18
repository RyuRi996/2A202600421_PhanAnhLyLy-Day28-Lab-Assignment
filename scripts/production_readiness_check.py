# scripts/production_readiness_check.py
import requests
import redis
import subprocess

results = {}


def check(name, fn):
    try:
        fn()
        results[name] = "PASS"
        print(f"  [PASS] {name}")
    except Exception as e:
        results[name] = f"FAIL: {e}"
        print(f"  [FAIL] {name}: {e}")


print("\n=== RELIABILITY ===")
check("Health check endpoint", lambda:
    requests.get("http://localhost:8000/health", timeout=5).raise_for_status())
check("API Gateway responds", lambda:
    requests.get("http://localhost:8000/docs", timeout=5).raise_for_status())

print("\n=== OBSERVABILITY ===")
check("Prometheus up", lambda:
    requests.get("http://localhost:9090/-/healthy", timeout=5).raise_for_status())
check("Grafana up", lambda:
    requests.get("http://localhost:3000/api/health", timeout=5).raise_for_status())
check("Metrics endpoint exposed", lambda:
    requests.get("http://localhost:8000/metrics", timeout=5).raise_for_status())

print("\n=== SECURITY ===")


def check_unauthorized():
    r = requests.get("http://localhost:8000/admin", timeout=5)
    assert r.status_code in [401, 403, 404]


check("Unauthorized request rejected", check_unauthorized)

print("\n=== VECTOR STORE ===")
check("Qdrant healthy", lambda:
    requests.get("http://localhost:6333/healthz", timeout=5).raise_for_status())


def check_collection_exists():
    r = requests.get("http://localhost:6333/collections/documents", timeout=5)
    r.raise_for_status()


check("Collection exists", check_collection_exists)

print("\n=== FEATURE STORE ===")
check("Redis reachable", lambda:
    redis.Redis(host="localhost", port=6379, socket_timeout=5).ping())

print("\n=== KAFKA ===")


def check_kafka_topics():
    # Try multiple possible container name formats
    container_names = [
        "2a202600421_phananhlyly-day28-lab-assignment-kafka-1",
        "lab28-kafka-1",
        "kafka-1",
    ]
    for name in container_names:
        result = subprocess.run(
            ["docker", "exec", name, "kafka-topics", "--list",
             "--bootstrap-server", "localhost:9092"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            assert "data.raw" in result.stdout, f"Topic 'data.raw' not found. Topics: {result.stdout}"
            return
    raise RuntimeError("Could not find Kafka container")


check("Kafka topics exist", check_kafka_topics)

# Summary
passed = sum(1 for v in results.values() if v == "PASS")
total = len(results)
score = (passed / total) * 100
print(f"\n{'='*40}")
print(f"Production Readiness Score: {passed}/{total} = {score:.0f}%")
print(f"Target: >80% — Status: {'READY' if score >= 80 else 'NOT READY'}")
