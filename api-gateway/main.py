from fastapi import FastAPI, Request, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
import httpx, os, time

app = FastAPI(title="AI Platform API Gateway")
Instrumentator().instrument(app).expose(app)

VLLM_URL = os.environ.get("VLLM_URL", "http://placeholder:8001")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")


@app.post("/api/v1/chat")
async def chat(request: Request):
    body = await request.json()
    if "query" not in body:
        raise HTTPException(status_code=422, detail="Field 'query' is required")

    query = body["query"]
    start = time.time()
    context = []

    # 1. Vector search (graceful — Qdrant may have no collection yet)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            search_resp = await client.post(
                f"{QDRANT_URL}/collections/documents/points/search",
                json={"vector": body.get("embedding", [0.0] * 384), "limit": 3}
            )
            if search_resp.status_code == 200:
                context = search_resp.json().get("result", [])
    except Exception:
        pass  # vector store not ready yet

    # 2. LLM inference
    prompt = f"Context: {context}\n\nQuery: {query}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            llm_resp = await client.post(
                f"{VLLM_URL}/v1/chat/completions",
                json={
                    "model": "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            llm_resp.raise_for_status()
            result = llm_resp.json()
    except Exception as e:
        latency = (time.time() - start) * 1000
        return {
            "answer": f"[LLM unavailable — Kaggle tunnel not connected]: {str(e)}",
            "latency_ms": round(latency, 2),
            "model": "unavailable"
        }

    latency = (time.time() - start) * 1000
    result_data = llm_resp.json()

    return {
        "answer": result_data["choices"][0]["message"]["content"],
        "latency_ms": round(latency, 2),
        "model": result_data.get("model", "unknown")
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "AI Platform API Gateway", "status": "running"}
