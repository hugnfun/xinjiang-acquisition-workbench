"""单消费者后台任务队列。

所有抓取和 LLM 任务串行执行，避免 SQLite 写竞争和多个模型请求互相抢资源。
队列统一兜底 running/done/failed 状态；具体 job 仍可写更细的进度与摘要。
"""
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue
import threading
from typing import Any, Callable


@dataclass
class JobHandle:
    _event: threading.Event = field(default_factory=threading.Event)
    _result: Any = None
    _error: BaseException | None = None

    def result(self, timeout: float | None = None):
        if not self._event.wait(timeout):
            raise TimeoutError("job queue wait timed out")
        if self._error is not None:
            raise self._error
        return self._result


@dataclass
class _WorkItem:
    job_id: int
    func: Callable
    args: tuple
    kwargs: dict
    handle: JobHandle


_queue: Queue[_WorkItem] = Queue()
_thread: threading.Thread | None = None
_start_lock = threading.Lock()


def _update_job(job_id: int, **fields) -> None:
    from sidecar.db.models import ScrapeJob
    from sidecar.db.session import session_scope

    with session_scope() as s:
        job = s.get(ScrapeJob, job_id)
        if not job:
            return
        for key, value in fields.items():
            setattr(job, key, value)


def _append_log(job_id: int, message: str, level: str = "info") -> None:
    from sidecar.db.models import JobLog
    from sidecar.db.session import session_scope

    with session_scope() as s:
        s.add(JobLog(job_id=job_id, level=level, message=message))


def _job_state(job_id: int) -> tuple[str | None, bool]:
    from sidecar.db.models import ScrapeJob
    from sidecar.db.session import session_scope

    with session_scope() as s:
        job = s.get(ScrapeJob, job_id)
        if not job:
            return None, False
        return job.status, bool(job.cancel_requested)


def cancellation_checkpoint(job_id: int) -> bool:
    """在阶段或批次边界协作式取消；进行中的网络请求会在返回后生效。"""
    status, requested = _job_state(job_id)
    if status == "cancelled":
        return True
    if not requested:
        return False
    _update_job(
        job_id,
        status="cancelled",
        error=None,
        finished_at=datetime.utcnow(),
    )
    _append_log(job_id, "任务已取消")
    return True


def _execute(item: _WorkItem) -> None:
    status, requested = _job_state(item.job_id)
    if status is None:
        item.handle._error = RuntimeError(f"job {item.job_id} not found")
        item.handle._event.set()
        return
    if status == "cancelled" or requested:
        cancellation_checkpoint(item.job_id)
        item.handle._event.set()
        return

    _update_job(
        item.job_id,
        status="running",
        error=None,
        started_at=datetime.utcnow(),
        finished_at=None,
    )
    try:
        item.handle._result = item.func(*item.args, **item.kwargs)
        status, _ = _job_state(item.job_id)
        if status in ("queued", "running"):
            _update_job(
                item.job_id,
                status="done",
                finished_at=datetime.utcnow(),
            )
    except BaseException as exc:
        item.handle._error = exc
        _update_job(
            item.job_id,
            status="failed",
            error=str(exc),
            finished_at=datetime.utcnow(),
        )
        _append_log(item.job_id, f"失败: {exc}", "error")
    finally:
        item.handle._event.set()


def start_worker() -> None:
    global _thread
    with _start_lock:
        if _thread and _thread.is_alive():
            return

        def _run() -> None:
            while True:
                item = _queue.get()
                try:
                    _execute(item)
                finally:
                    _queue.task_done()

        _thread = threading.Thread(
            target=_run, name="workbench-job-worker", daemon=True
        )
        _thread.start()


def submit(job_id: int, func: Callable, *args, **kwargs) -> JobHandle:
    start_worker()
    handle = JobHandle()
    _queue.put(_WorkItem(job_id, func, args, kwargs, handle))
    return handle
