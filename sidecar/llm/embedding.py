import numpy as np
from openai import OpenAI
from sidecar import config

def _get_client():
    return OpenAI(base_url=config.EMBEDDING_API_BASE, api_key=config.EMBEDDING_API_KEY)

def embed(text: str) -> np.ndarray:
    client = _get_client()
    resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=text)
    return np.array(resp.data[0].embedding, dtype=np.float32)

def embed_batch(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    client = _get_client()
    resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=texts)
    mat = np.array([d.embedding for d in resp.data], dtype=np.float32)
    return mat
