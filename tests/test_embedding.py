import numpy as np
from sidecar.llm import embedding as E

def test_embed_returns_float32_vector(monkeypatch):
    fake_vec = [0.1, 0.2, 0.3]
    def fake_create(model, input):
        class R:
            data = [type("D",(),{"embedding":fake_vec})()]
        return R()
    class Client:
        @property
        def embeddings(self): return self
        def create(self, model, input): return fake_create(model, input)
    monkeypatch.setattr(E, "_get_client", lambda: Client())
    vec = E.embed("测试")
    assert isinstance(vec, np.ndarray)
    assert vec.dtype == np.float32
    assert list(vec) == [0.1, 0.2, 0.3]

def test_embed_batch_returns_2d(monkeypatch):
    def fake_create(model, input):
        class R:
            data = [type("D",(),{"embedding":[float(i),0.1]})() for i in range(len(input))]
        return R()
    class Client:
        @property
        def embeddings(self): return self
        def create(self, model, input): return fake_create(model, input)
    monkeypatch.setattr(E, "_get_client", lambda: Client())
    mat = E.embed_batch(["a","b","c"])
    assert mat.shape == (3, 2)
    assert mat.dtype == np.float32
