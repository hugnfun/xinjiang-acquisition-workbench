import numpy as np

def cosine_matrix(vectors: np.ndarray) -> np.ndarray:
    """N×N 余弦相似度矩阵。vectors: (N, D) float。"""
    if vectors.shape[0] == 0:
        return np.zeros((0, 0), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # 防除零
    normed = vectors / norms
    return (normed @ normed.T).astype(np.float32)

def cluster_by_similarity(vectors: np.ndarray, threshold: float) -> list[int]:
    """余弦相似度 > threshold 的连通成簇。返回每个向量的簇 id（0-based，连续编号）。"""
    n = vectors.shape[0]
    if n == 0:
        return []
    sim = cosine_matrix(vectors)
    # 邻接：相似度 > threshold
    adj = (sim > threshold)
    # 连通分量（BFS）
    visited = [False] * n
    labels = [-1] * n
    cluster_id = 0
    for i in range(n):
        if visited[i]:
            continue
        # BFS 从 i 出发
        stack = [i]
        while stack:
            node = stack.pop()
            if visited[node]:
                continue
            visited[node] = True
            labels[node] = cluster_id
            for j in range(n):
                if adj[node, j] and not visited[j]:
                    stack.append(j)
        cluster_id += 1
    return labels
