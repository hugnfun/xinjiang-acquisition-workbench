import numpy as np
from sidecar.cluster import cosine as C

def test_cosine_matrix_shape():
    v = np.array([[1,0],[0,1],[1,1]], dtype=np.float32)
    m = C.cosine_matrix(v)
    assert m.shape == (3, 3)
    # 对角线 = 1
    assert abs(m[0,0] - 1.0) < 1e-5

def test_cluster_groups_similar():
    # 3 个向量：前2个相似(方向接近)，第3个不同
    v = np.array([[1.0, 0.0], [0.99, 0.01], [0.0, 1.0]], dtype=np.float32)
    labels = C.cluster_by_similarity(v, threshold=0.78)
    assert len(labels) == 3
    # 前2个同簇
    assert labels[0] == labels[1]
    # 第3个不同簇
    assert labels[2] != labels[0]

def test_cluster_all_similar_one_cluster():
    v = np.array([[1.0,0.0],[1.0,0.01],[0.99,0.0]], dtype=np.float32)
    labels = C.cluster_by_similarity(v, threshold=0.78)
    assert len(set(labels)) == 1

def test_cluster_all_different():
    v = np.array([[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]], dtype=np.float32)
    labels = C.cluster_by_similarity(v, threshold=0.78)
    assert len(set(labels)) == 3

def test_cluster_empty():
    v = np.zeros((0, 0), dtype=np.float32)
    labels = C.cluster_by_similarity(v, threshold=0.78)
    assert labels == []
