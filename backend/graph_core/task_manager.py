"""
Async task manager for long-running backend jobs.
"""

import asyncio
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus
    progress: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    user_id: int = 0
    input_summary: str = ""
    event_seq: int = 0
    events: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_time": self.elapsed_time,
            "input_summary": self.input_summary,
        }

    @property
    def elapsed_time(self) -> float:
        end_time = self.completed_at or time.time()
        start_time = self.started_at or self.created_at
        return round(end_time - start_time, 2)


class AsyncTaskManager:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._tasks: Dict[str, TaskInfo] = {}
        self._tasks_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._task_timeout = 300
        self._cleanup_interval = 600
        self._cleanup_retention = 1800
        self._cleanup_task_started = False
        self._initialized = True

    def _start_cleanup_task(self):
        if self._cleanup_task_started:
            return

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        asyncio.create_task(self._cleanup_loop())
        self._cleanup_task_started = True

    def create_task(self, user_id: int, input_summary: str = "") -> TaskInfo:
        self._start_cleanup_task()

        task = TaskInfo(
            task_id=f"task_{uuid.uuid4().hex[:16]}",
            status=TaskStatus.PENDING,
            user_id=user_id,
            input_summary=input_summary[:100],
        )
        with self._tasks_lock:
            self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def complete_task(self, task_id: str, result: dict):
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.progress = 100
            if task.started_at is None:
                task.started_at = task.created_at
            task.completed_at = time.time()

    def fail_task(self, task_id: str, error: str):
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            task.status = TaskStatus.FAILED
            task.error = error
            if task.started_at is None:
                task.started_at = task.created_at
            task.completed_at = time.time()

    def update_task_progress(self, task_id: str, progress: int):
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            task.progress = min(100, max(0, progress))
            if task.progress > 0 and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PROCESSING
            if task.progress > 0 and task.started_at is None:
                task.started_at = time.time()

    def publish_task_event(self, task_id: str, event: dict):
        """Append a lightweight event to task stream for WebSocket consumers."""
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            task.event_seq += 1
            payload = {
                "seq": task.event_seq,
                "timestamp": time.time(),
            }
            payload.update(event)
            task.events.append(payload)

            # Keep memory bounded for long tasks.
            if len(task.events) > 1200:
                task.events = task.events[-800:]

    def get_task_events(self, task_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if not task:
                return []

            return [dict(event) for event in task.events if int(event.get("seq", 0)) > after_seq]

    def _run_sync_in_executor(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(self._executor, lambda: fn(*args, **kwargs))

    async def execute_task(
        self,
        task_id: str,
        workflow_func: Callable,
        *args,
        **kwargs,
    ):
        task = self.get_task(task_id)
        if not task:
            return

        task.status = TaskStatus.PROCESSING
        task.started_at = time.time()
        task.progress = 10

        try:
            task.progress = 30
            result = await asyncio.wait_for(
                self._run_sync_in_executor(workflow_func, *args, **kwargs),
                timeout=self._task_timeout,
            )
            if isinstance(result, dict):
                self.complete_task(task_id, result)
            else:
                self.complete_task(task_id, {"output": str(result)})
        except asyncio.TimeoutError:
            with self._tasks_lock:
                current_task = self._tasks.get(task_id)
                if current_task:
                    current_task.status = TaskStatus.TIMEOUT
                    current_task.error = "Task execution timed out"
                    current_task.completed_at = time.time()
        except Exception as exc:
            self.fail_task(task_id, str(exc))

    def get_user_tasks(self, user_id: int, limit: int = 20) -> list:
        with self._tasks_lock:
            user_tasks = [task for task in self._tasks.values() if task.user_id == user_id]

        user_tasks.sort(key=lambda item: item.created_at, reverse=True)
        return [task.to_dict() for task in user_tasks[:limit]]

    def cancel_task(self, task_id: str) -> bool:
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.PENDING:
                return False

            task.status = TaskStatus.FAILED
            task.error = "Task was cancelled"
            task.completed_at = time.time()
            return True

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(self._cleanup_interval)
            self._cleanup_expired_tasks()

    def _cleanup_expired_tasks(self):
        cutoff = time.time() - self._cleanup_retention
        expired_task_ids = []

        with self._tasks_lock:
            for task_id, task in self._tasks.items():
                if task.status not in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT}:
                    continue
                completed_at = task.completed_at or task.created_at
                if completed_at < cutoff:
                    expired_task_ids.append(task_id)

            for task_id in expired_task_ids:
                self._tasks.pop(task_id, None)


task_manager = AsyncTaskManager()
