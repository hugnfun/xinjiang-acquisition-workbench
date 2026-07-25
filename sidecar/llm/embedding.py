import numpy as np
from openai import OpenAI
from sidecar import config

def _get_client():
    return OpenAI(base_url=config.EMBEDDING_API_BASE, api_key=config.EMBEDDING_API_KEY, timeout=30, max_retries=2)

def embed(text: str) -> np.ndarray:
    client = _get_client()
    resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=text)
    return np.array(resp.data[0].embedding, dtype=np.float32)

def embed_batch(texts: list[str], batch_size: int = 50) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    client = _get_client()
    all_vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=batch)
        all_vecs.extend(d.embedding for d in resp.data)
    return np.array(all_vecs, dtype=np.float32)
