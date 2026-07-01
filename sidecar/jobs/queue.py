import asyncio
import threading

_queue: asyncio.Queue = None
_loop: asyncio.AbstractEventLoop = None
_thread: threading.Thread = None

def start_worker():
    global _queue, _loop, _thread
    if _thread and _thread.is_alive():
        return
    _queue = asyncio.Queue()
    _loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()

def submit(coro):
    if _loop is None:
        start_worker()
    fut = asyncio.run_coroutine_threadsafe(coro, _loop)
    return fut
