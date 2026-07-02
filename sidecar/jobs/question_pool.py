from datetime import datetime
from sidecar.db.session import get_session, session_scope
from sidecar.db.models import (Comment, Question, QuestionCluster, ScrapeJob,
                               JobLog)
from sidecar.llm import task_client as tc
from sidecar.llm import embedding as emb
from sidecar.cluster.cosine import cluster_by_similarity
from sidecar import config

BATCH = 20


def _log(job_id, msg, level="info"):
    """独立短 session 写日志并立即 commit。

    好处：(1) 日志即时落库可见——监控/前端不用等 stage 结束才看到；
    (2) 不在长 LLM 调用期间占着连接。
    """
    with session_scope() as s:
        s.add(JobLog(job_id=job_id, level=level, message=msg))


def _set_job(job_id, **fields):
    """短 session 更新 ScrapeJob 字段并 commit。"""
    with session_scope() as s:
        job = s.query(ScrapeJob).get(job_id)
        for k, v in fields.items():
            setattr(job, k, v)


def _batched(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def run_question_pool_job(job_id: int):
    _set_job(job_id, status="running", started_at=datetime.utcnow())
    _log(job_id, "开始问题池冷启动")
    try:
        # Stage 1: 过滤"是不是问题"（短 session 读评论，LLM 调用无 session）
        with session_scope() as s:
            comments = s.query(Comment).filter(Comment.is_reply == False).all()
            # 提取标量到普通 tuple，session 关闭后仍可用
            comment_data = [(c.id, (c.text or "").strip()) for c in comments]
        _log(job_id, f"待过滤评论 {len(comment_data)} 条")
        questions_data = []
        for batch in _batched(comment_data, BATCH):
            non_empty = [(cid, txt) for cid, txt in batch if txt]
            payload = [{"raw": txt} for cid, txt in non_empty]
            if not payload:
                continue
            try:
                results = tc.filter_questions(payload)
            except Exception as e:
                _log(job_id, f"过滤批次失败: {e}", "error")
                continue
            for r, (cid, txt) in zip(results, non_empty):
                if r.get("is_question"):
                    questions_data.append({"raw": r.get("raw", txt), "comment_id": cid})
        _log(job_id, f"Stage1 过滤出 {len(questions_data)} 个问题")
        if not questions_data:
            _set_job(job_id, status="done", result_summary={"questions": 0, "clusters": 0},
                     finished_at=datetime.utcnow())
            _log(job_id, "无问题，完成")
            return

        # Stage 2: 归一化（无 session）
        for batch in _batched(questions_data, BATCH):
            try:
                normed = tc.normalize_questions([{"raw": q["raw"]} for q in batch])
            except Exception as e:
                _log(job_id, f"归一化批次失败: {e}", "error")
                continue
            for q, n in zip(batch, normed):
                q["normalized"] = n.get("normalized", q["raw"])
        for q in questions_data:
            q.setdefault("normalized", q["raw"])
        _log(job_id, "Stage2 归一化完成")

        # Stage 3: embedding（无 session）
        texts = [q["normalized"] for q in questions_data]
        try:
            mat = emb.embed_batch(texts)
        except Exception as e:
            _set_job(job_id, status="failed", error=f"embedding 失败: {e}",
                     finished_at=datetime.utcnow())
            _log(job_id, f"embedding 失败: {e}", "error")
            return
        _log(job_id, f"Stage3 embedding 完成 ({mat.shape})")

        # Stage 4: 聚类 + 落库（一个短 session 批量写）
        labels = cluster_by_similarity(mat, config.CLUSTER_SIMILARITY_THRESHOLD)
        cluster_id_map = {}  # local_label -> db cluster_id
        with session_scope() as s:
            for q, vec, label in zip(questions_data, mat, labels):
                if label not in cluster_id_map:
                    cl = QuestionCluster(name="", description="", question_count=0)
                    s.add(cl); s.flush()
                    cluster_id_map[label] = cl.id
                cid = cluster_id_map[label]
                s.add(Question(
                    normalized_text=q["normalized"], raw_text=q["raw"],
                    source_ref=q["comment_id"], source_type="comment",
                    embedding=vec.tobytes(), cluster_id=cid,
                ))
        # 更新簇计数（短 session）
        with session_scope() as s:
            for cid in cluster_id_map.values():
                cnt = s.query(Question).filter_by(cluster_id=cid).count()
                cl = s.query(QuestionCluster).get(cid)
                if cl:
                    cl.question_count = cnt
        _log(job_id, f"Stage4 聚类完成，{len(cluster_id_map)} 簇")

        # Stage 5: 命名（每簇：短 session 取样本→无 session 跑 LLM→短 session 写名）
        for cid in cluster_id_map.values():
            with session_scope() as s:
                samples = [q.raw_text
                           for q in s.query(Question).filter_by(cluster_id=cid).limit(5).all()]
            if not samples:
                continue
            try:
                named = tc.name_cluster(samples)
            except Exception as e:
                _log(job_id, f"簇 {cid} 命名失败: {e}", "error")
                named = {"name": "", "description": ""}
            with session_scope() as s:
                cl = s.query(QuestionCluster).get(cid)
                if cl:
                    cl.name = named.get("name", "")
                    cl.description = named.get("description", "")
        _log(job_id, "Stage5 命名完成")

        _set_job(job_id, status="done",
                 result_summary={"questions": len(questions_data),
                                 "clusters": len(cluster_id_map)},
                 finished_at=datetime.utcnow())
        _log(job_id, f"完成：{len(questions_data)} 问题，{len(cluster_id_map)} 簇")
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e), finished_at=datetime.utcnow())
        _log(job_id, f"失败: {e}", "error")
