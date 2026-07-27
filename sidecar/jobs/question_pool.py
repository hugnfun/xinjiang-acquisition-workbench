from datetime import datetime
import numpy as np
from sidecar.db.session import session_scope
from sidecar.db.models import (Comment, Question, QuestionCluster, ScrapeJob,
                               JobLog)
from sidecar.llm import task_client as tc
from sidecar.llm import embedding as emb
from sidecar.cluster.cosine import cluster_by_similarity
from sidecar.jobs.queue import cancellation_checkpoint
from sidecar.jobs.usage import job_usage_accumulator
from sidecar import config

BATCH = 50


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


def _sync_legacy_question_status(s):
    """兼容迁移前或测试中手工创建的 Question。"""
    referenced = [
        row[0] for row in s.query(Question.source_ref).filter(
            Question.source_type == "comment",
            Question.source_ref.isnot(None),
        ).all()
    ]
    if referenced:
        s.query(Comment).filter(
            Comment.id.in_(referenced),
            Comment.question_status == "pending",
        ).update(
            {
                Comment.question_status: "question",
                Comment.question_processed_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )


def _mark_comments(comment_ids: list[int], status: str):
    if not comment_ids:
        return
    with session_scope() as s:
        s.query(Comment).filter(Comment.id.in_(comment_ids)).update(
            {
                Comment.question_status: status,
                Comment.question_processed_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )


def _filter_candidates(job_id: int, comment_data):
    """过滤问题并持久化非问题游标；失败批次保持 pending 供重试。

    已标记为 question_pending 的评论（上次过滤判为问题但未完成后续阶段）
    直接收集，不再重复调用 LLM。
    """
    questions_data = []
    failed_batches = 0
    # 分离待过滤(pending)和已过滤(question_pending)
    to_filter = [(cid, txt) for cid, txt in comment_data]
    for batch in _batched(comment_data, BATCH):
        if cancellation_checkpoint(job_id):
            return None
        empty_ids = [cid for cid, txt in batch if not txt]
        _mark_comments(empty_ids, "excluded")
        non_empty = [(cid, txt) for cid, txt in batch if txt]
        payload = [{"raw": txt} for cid, txt in non_empty]
        if not payload:
            continue
        try:
            results = tc.filter_questions(payload)
        except Exception as e:
            failed_batches += 1
            _log(job_id, f"过滤批次失败: {e}", "error")
            continue
        if len(results) != len(non_empty):
            failed_batches += 1
            _log(
                job_id,
                f"过滤结果数量不匹配：请求 {len(non_empty)}，返回 {len(results)}",
                "error",
            )
        not_question_ids = []
        question_ids = []
        for r, (cid, txt) in zip(results, non_empty):
            if r.get("is_question"):
                questions_data.append({
                    "raw": r.get("raw", txt), "comment_id": cid
                })
                question_ids.append(cid)
            else:
                not_question_ids.append(cid)
        _mark_comments(not_question_ids, "not_question")
        _mark_comments(question_ids, "question_pending")
    return questions_data, failed_batches


def run_question_pool_job(job_id: int):
    usage = job_usage_accumulator(job_id)
    with tc.track_usage(usage):
        return _run_question_pool_job(job_id)


def _run_question_pool_job(job_id: int):
    _set_job(job_id, status="running", started_at=datetime.utcnow())
    _log(job_id, "开始问题池冷启动")
    try:
        with session_scope() as s:
            has_questions = s.query(Question).count() > 0
        if has_questions:
            error = "问题池已有数据，冷启动不可重复执行；请使用增量更新"
            _set_job(
                job_id, status="failed", error=error,
                finished_at=datetime.utcnow(),
            )
            _log(job_id, error, "error")
            return
        # Stage 1: 过滤"是不是问题"（短 session 读评论，LLM 调用无 session）
        with session_scope() as s:
            comments = s.query(Comment).filter(
                Comment.is_reply == False,
                Comment.question_status == "pending",
            ).all()
            # 提取标量到普通 tuple，session 关闭后仍可用
            comment_data = [(c.id, (c.text or "").strip()) for c in comments]
        _log(job_id, f"待过滤评论 {len(comment_data)} 条")
        filtered = _filter_candidates(job_id, comment_data)
        if filtered is None:
            return
        questions_data, failed_filter_batches = filtered
        _log(job_id, f"Stage1 过滤出 {len(questions_data)} 个问题")
        if not questions_data:
            if failed_filter_batches:
                error = f"{failed_filter_batches} 个过滤批次失败，评论保留待重试"
                _set_job(
                    job_id, status="failed", error=error,
                    result_summary={"questions": 0, "clusters": 0},
                    finished_at=datetime.utcnow(),
                )
                _log(job_id, error, "error")
                return
            _set_job(job_id, status="done", result_summary={"questions": 0, "clusters": 0},
                     finished_at=datetime.utcnow())
            _log(job_id, "无问题，完成")
            return

        # Stage 2: 归一化（无 session）
        for batch in _batched(questions_data, BATCH):
            if cancellation_checkpoint(job_id):
                return
            try:
                normed = tc.normalize_questions([{"raw": q["raw"]} for q in batch])
                for q, n in zip(batch, normed):
                    q["normalized"] = n.get("normalized", q["raw"])
            except Exception as e:
                _log(job_id, f"归一化批次失败(用原文): {e}", "warning")
                # 归一化失败不跳过，用 raw_text 兜底，embedding 聚类仍能工作
        for q in questions_data:
            q.setdefault("normalized", q["raw"])
        _log(job_id, "Stage2 归一化完成")

        # Stage 3: embedding（无 session）
        texts = [q["normalized"] for q in questions_data]
        if cancellation_checkpoint(job_id):
            return
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
                comment = s.get(Comment, q["comment_id"])
                if comment:
                    comment.question_status = "question"
                    comment.question_processed_at = datetime.utcnow()
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
            if cancellation_checkpoint(job_id):
                return
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

        result_summary = {
            "questions": len(questions_data),
            "clusters": len(cluster_id_map),
        }
        if failed_filter_batches:
            result_summary["failed_filter_batches"] = failed_filter_batches
        _set_job(job_id, status="done",
                 result_summary=result_summary,
                 finished_at=datetime.utcnow())
        _log(job_id, f"完成：{len(questions_data)} 问题，{len(cluster_id_map)} 簇")
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e), finished_at=datetime.utcnow())
        _log(job_id, f"失败: {e}", "error")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """两向量的余弦相似度。"""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def run_question_pool_incremental(job_id: int):
    usage = job_usage_accumulator(job_id)
    with tc.track_usage(usage):
        return _run_question_pool_incremental(job_id)


def _run_question_pool_incremental(job_id: int):
    """增量更新问题池：只处理新评论，按质心分配到现有簇（sim>阈值）或建新簇。

    与全量冷启动的区别：不重跑已有问题、不重聚类、只命名新建簇。质心=簇内问题
    embedding 均值；新问题找最近质心，超阈值并入，否则新建。保留既有簇不动。
    """
    _set_job(job_id, status="running", started_at=datetime.utcnow())
    _log(job_id, "开始增量更新问题池")
    try:
        threshold = config.CLUSTER_SIMILARITY_THRESHOLD
        # 1. 现有簇质心 + 已处理 comment_id 集合 + 新评论
        with session_scope() as s:
            _sync_legacy_question_status(s)
            clusters = s.query(QuestionCluster).all()
            centroids: dict[int, np.ndarray] = {}  # cluster_id -> 质心
            for cl in clusters:
                qs = s.query(Question).filter_by(cluster_id=cl.id).all()
                if not qs:
                    continue
                vecs = np.array([np.frombuffer(q.embedding, dtype=np.float32) for q in qs])
                centroids[cl.id] = vecs.mean(axis=0)
            new_comments = s.query(Comment).filter(
                Comment.is_reply == False,
                Comment.question_status.in_(["pending", "question_pending"]),
            ).all()
            comment_data = [(c.id, (c.text or "").strip()) for c in new_comments]
            processed = s.query(Comment).filter(
                Comment.question_status != "pending"
            ).count()
        _log(job_id, f"增量：{len(comment_data)} 条新评论（已处理 {processed} 条）")
        if not comment_data:
            _set_job(job_id, status="done",
                     result_summary={"new_questions": 0, "merged": 0, "new_clusters": 0},
                     finished_at=datetime.utcnow())
            _log(job_id, "无新评论，完成")
            return

        # 2. 过滤 + 归一化 + embedding
        # 分离：pending 需要过滤，question_pending 直接收集
        with session_scope() as s:
            pending_ids = {c.id for c in s.query(Comment).filter(
                Comment.is_reply == False, Comment.question_status == "pending"
            ).all()}
        to_filter = [(cid, txt) for cid, txt in comment_data if cid in pending_ids]
        to_collect = [(cid, txt) for cid, txt in comment_data if cid not in pending_ids]
        questions_data = [{"raw": txt, "comment_id": cid} for cid, txt in to_collect]
        if to_collect:
            _log(job_id, f"捡回 {len(to_collect)} 条上次未完成的问题")
        filtered = _filter_candidates(job_id, to_filter)
        if filtered is None:
            return
        new_questions, failed_filter_batches = filtered
        questions_data.extend(new_questions)


        if not questions_data:
            if failed_filter_batches:
                error = f"{failed_filter_batches} 个过滤批次失败，评论保留待重试"
                _set_job(
                    job_id, status="failed", error=error,
                    result_summary={
                        "new_questions": 0, "merged": 0, "new_clusters": 0,
                    },
                    finished_at=datetime.utcnow(),
                )
                _log(job_id, error, "error")
                return
            _set_job(job_id, status="done",
                     result_summary={"new_questions": 0, "merged": 0, "new_clusters": 0},
                     finished_at=datetime.utcnow())
            _log(job_id, "新评论中无问题，完成")
            return
        for batch in _batched(questions_data, BATCH):
            if cancellation_checkpoint(job_id):
                return
            try:
                normed = tc.normalize_questions([{"raw": q["raw"]} for q in batch])
                for q, n in zip(batch, normed):
                    q["normalized"] = n.get("normalized", q["raw"])
            except Exception as e:
                _log(job_id, f"归一化批次失败(用原文): {e}", "warning")
                # 归一化失败不跳过，用 raw_text 兜底，embedding 聚类仍能工作
        for q in questions_data:
            q.setdefault("normalized", q["raw"])
        try:
            if cancellation_checkpoint(job_id):
                return
            mat = emb.embed_batch([q["normalized"] for q in questions_data])
        except Exception as e:
            _set_job(job_id, status="failed", error=f"embedding 失败: {e}",
                     finished_at=datetime.utcnow())
            _log(job_id, f"embedding 失败: {e}", "error")
            return

        # 3. 质心分配：新问题找最近质心，sim>阈值→并入；否则新建簇
        merged = 0
        new_cluster_ids: list[int] = []
        with session_scope() as s:
            for q, vec in zip(questions_data, mat):
                best_cid, best_sim = None, -1.0
                for cid, cent in centroids.items():
                    sim = _cosine(vec, cent)
                    if sim > best_sim:
                        best_sim, best_cid = sim, cid
                if best_cid is not None and best_sim > threshold:
                    cid = best_cid
                    merged += 1
                else:
                    cl = QuestionCluster(name="", description="", question_count=0)
                    s.add(cl); s.flush()
                    cid = cl.id
                    centroids[cid] = vec  # 新簇质心=首个向量
                    new_cluster_ids.append(cid)
                # 跳过已入库的（防 UNIQUE constraint 冲突）
                existing = s.query(Question).filter_by(
                    source_type="comment", source_ref=q["comment_id"]
                ).first()
                if existing:
                    continue
                s.add(Question(
                    normalized_text=q["normalized"], raw_text=q["raw"],
                    source_ref=q["comment_id"], source_type="comment",
                    embedding=vec.tobytes(), cluster_id=cid,
                ))
                comment = s.get(Comment, q["comment_id"])
                if comment:
                    comment.question_status = "question"
                    comment.question_processed_at = datetime.utcnow()
        _log(job_id, f"增量分配完成：{len(questions_data)} 新问题，并入 {merged}，新建 {len(new_cluster_ids)} 簇")

        # 4. 更新受影响簇计数
        affected = set(new_cluster_ids) | {cid for cid in centroids}  # 简化：全部刷新
        with session_scope() as s:
            for cid in list(affected):
                cl = s.query(QuestionCluster).get(cid)
                if cl:
                    cl.question_count = s.query(Question).filter_by(cluster_id=cid).count()

        # 5. 只命名新建簇（既有簇名不动，省 MiniMax）
        for cid in new_cluster_ids:
            if cancellation_checkpoint(job_id):
                return
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

        result_summary = {
            "new_questions": len(questions_data),
            "merged": merged,
            "new_clusters": len(new_cluster_ids),
        }
        if failed_filter_batches:
            result_summary["failed_filter_batches"] = failed_filter_batches
        _set_job(job_id, status="done",
                 result_summary=result_summary,
                 finished_at=datetime.utcnow())
        _log(job_id, f"完成：新增 {len(questions_data)} 问题，并入 {merged}，新建 {len(new_cluster_ids)} 簇")
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e), finished_at=datetime.utcnow())
        _log(job_id, f"失败: {e}", "error")
