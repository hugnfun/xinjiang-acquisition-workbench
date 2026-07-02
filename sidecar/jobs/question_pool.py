from datetime import datetime
from sidecar.db.session import get_session
from sidecar.db.models import (Comment, Question, QuestionCluster, ScrapeJob,
                               JobLog)
from sidecar.llm import task_client as tc
from sidecar.llm import embedding as emb
from sidecar.cluster.cosine import cluster_by_similarity
from sidecar import config

BATCH = 20


def _log(s, job_id, msg, level="info"):
    s.add(JobLog(job_id=job_id, level=level, message=msg))


def _batched(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def run_question_pool_job(job_id: int):
    s = get_session()
    job = s.query(ScrapeJob).get(job_id)
    job.status = "running"
    job.started_at = datetime.utcnow()
    _log(s, job_id, "开始问题池冷启动")
    s.commit()
    try:
        # Stage 1: 过滤"是不是问题"（仅顶层评论，跳过回复与空文本）
        comments = s.query(Comment).filter(Comment.is_reply == False).all()
        _log(s, job_id, f"待过滤评论 {len(comments)} 条")
        questions_data = []
        for batch in _batched(comments, BATCH):
            # 保留 (comment, raw) 配对，过滤空文本；payload 与 non_empty
            # 按位置对齐，确保 filter_questions 返回与输入一一对应。
            pairs = [(c, (c.text or "").strip()) for c in batch]
            non_empty = [c for c, txt in pairs if txt]
            payload = [{"raw": txt} for c, txt in pairs if txt]
            if not payload:
                continue
            try:
                results = tc.filter_questions(payload)
            except Exception as e:
                _log(s, job_id, f"过滤批次失败: {e}", "error")
                s.commit()
                continue
            # results 与 non_empty 按位置对齐（payload 顺序即 non_empty 顺序）
            for r, c in zip(results, non_empty):
                if r.get("is_question"):
                    questions_data.append({"raw": r.get("raw", ""), "comment_id": c.id})
        _log(s, job_id, f"Stage1 过滤出 {len(questions_data)} 个问题")
        s.commit()
        if not questions_data:
            job.status = "done"
            job.result_summary = {"questions": 0, "clusters": 0}
            _log(s, job_id, "无问题，完成")
            return

        # Stage 2: 归一化
        for batch in _batched(questions_data, BATCH):
            try:
                normed = tc.normalize_questions([{"raw": q["raw"]} for q in batch])
            except Exception as e:
                _log(s, job_id, f"归一化批次失败: {e}", "error")
                s.commit()
                continue
            for q, n in zip(batch, normed):
                q["normalized"] = n.get("normalized", q["raw"])
        # 批次失败时兜底：未归一化的回退到 raw
        for q in questions_data:
            q.setdefault("normalized", q["raw"])
        _log(s, job_id, "Stage2 归一化完成")

        # Stage 3: embedding
        texts = [q["normalized"] for q in questions_data]
        try:
            mat = emb.embed_batch(texts)
        except Exception as e:
            job.status = "failed"
            job.error = f"embedding 失败: {e}"
            _log(s, job_id, job.error, "error")
            job.finished_at = datetime.utcnow()
            s.commit()
            return
        _log(s, job_id, f"Stage3 embedding 完成 ({mat.shape})")

        # Stage 4: 聚类 + 落库
        labels = cluster_by_similarity(mat, config.CLUSTER_SIMILARITY_THRESHOLD)
        cluster_id_map = {}  # local_label -> db cluster_id
        for q, vec, label in zip(questions_data, mat, labels):
            if label not in cluster_id_map:
                cl = QuestionCluster(name="", description="", question_count=0)
                s.add(cl); s.flush()
                cluster_id_map[label] = cl.id
            cid = cluster_id_map[label]
            qrow = Question(
                normalized_text=q["normalized"], raw_text=q["raw"],
                source_ref=q["comment_id"], source_type="comment",
                embedding=vec.tobytes(), cluster_id=cid,
            )
            s.add(qrow)
        s.commit()
        # 更新簇计数
        for cid in cluster_id_map.values():
            cnt = s.query(Question).filter_by(cluster_id=cid).count()
            cl = s.query(QuestionCluster).get(cid)
            cl.question_count = cnt
        s.commit()
        _log(s, job_id, f"Stage4 聚类完成，{len(cluster_id_map)} 簇")

        # Stage 5: 命名（每簇取至多 5 条样本）
        for cid in cluster_id_map.values():
            samples = [q.raw_text
                       for q in s.query(Question).filter_by(cluster_id=cid).limit(5).all()]
            if not samples:
                continue
            try:
                named = tc.name_cluster(samples)
            except Exception as e:
                _log(s, job_id, f"簇 {cid} 命名失败: {e}", "error")
                named = {"name": "", "description": ""}
            cl = s.query(QuestionCluster).get(cid)
            cl.name = named.get("name", "")
            cl.description = named.get("description", "")
            s.commit()
        _log(s, job_id, "Stage5 命名完成")

        job.status = "done"
        job.result_summary = {"questions": len(questions_data),
                              "clusters": len(cluster_id_map)}
        _log(s, job_id, f"完成：{len(questions_data)} 问题，{len(cluster_id_map)} 簇")
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        _log(s, job_id, f"失败: {e}", "error")
    finally:
        job.finished_at = datetime.utcnow()
        s.commit()
