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


def test_chaining_transitive_merge_documents_threshold_trap():
    """B2 发现：聚类是连通分量(传递闭包)——A~B 且 B~C 即同簇，即使 A~C 低于阈值。

    降阈值会链式合并：大簇越滚越大、单问题簇占比不降。这是「不要靠调低阈值
    合并单问题簇」的算法依据，锁住以防回退。
    """
    # A~B 高(0.99), B~C 中(0.85), A~C 低(0.5)；阈值 0.8 时 A~B、B~C 连通 → 三者同簇
    import math
    def _vec(angle_deg):
        r = math.radians(angle_deg)
        return np.array([math.cos(r), math.sin(r)], dtype=np.float32)
    # 角度 0°/30°/60°：相邻相似 cos(30°)≈0.866>0.78 连通，首尾 A,C 差 60° cos=0.5<0.78
    v = np.array([_vec(0), _vec(30), _vec(60)])
    sim_ac = C.cosine_matrix(v)[0, 2]
    assert sim_ac < 0.78  # A 与 C 本身低于阈值
    labels = C.cluster_by_similarity(v, threshold=0.78)
    # 但经 B 传递连通 → 三个同簇（链式）
    assert labels[0] == labels[1] == labels[2], "A,B,C 经传递闭包应同簇"
