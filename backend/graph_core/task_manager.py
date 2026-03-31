"""
异步任务管理器
管理 LangGraph 工作流的异步执行
支持任务队列、状态跟踪、结果缓存
"""
import asyncio
import uuid
import time
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"           # 等待中
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    TIMEOUT = "timeout"           # 超时


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    status: TaskStatus
    progress: int = 0            # 进度 0-100
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    user_id: int = 0
    input_summary: str = ""      # 输入内容摘要

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_time": self._get_elapsed_time(),
            "input_summary": self.input_summary
        }

    def _get_elapsed_time(self) -> float:
        """获取已耗时（秒）"""
        end_time = self.completed_at or time.time()
        start_time = self.started_at or self.created_at
        return round(end_time - start_time, 2)


class AsyncTaskManager:
    """
    异步任务管理器
    单例模式，全局管理所有异步任务
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._tasks: Dict[str, TaskInfo] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._task_timeout = 300  # 5分钟超时
        self._cleanup_interval = 600  # 10分钟清理一次
        self._initialized = True
        self._cleanup_task_started = False

    def _start_cleanup_task(self):
        """延迟启动清理任务，确保事件循环已运行"""
        if not self._cleanup_task_started:
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self._cleanup_loop())
                self._cleanup_task_started = True
            except RuntimeError:
                # 没有运行的事件循环，跳过启动清理任务
                pass

    def create_task(self, user_id: int, input_summary: str = "") -> TaskInfo:
        """创建新任务"""
        # 确保清理任务已启动
        self._start_cleanup_task()

        task_id = f"task_{uuid.uuid4().hex[:16]}"
        task = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            user_id=user_id,
            input_summary=input_summary[:100]  # 限制长度
        )
        self._tasks[task_id] = task
        return task

    async def _cleanup_loop(self):
        """定期清理过期任务"""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self._cleanup_expired_tasks()

    async def _cleanup_expired_tasks(self):
        """清理已完成的过期任务"""
        current_time = time.time()
        expired_tasks = []

        for task_id, task in self._tasks.items():
            # 已完成/失败且超过30分钟的
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT]:
                if current_time - (task.completed_at or task.created_at) > 1800:
                    expired_tasks.append(task_id)

        for task_id in expired_tasks:
            del self._tasks[task_id]

        if expired_tasks:
            print(f"[TaskManager] 清理 {len(expired_tasks)} 个过期任务")

    def create_task(self, user_id: int, input_summary: str = "") -> TaskInfo:
        """创建新任务"""
        task_id = f"task_{uuid.uuid4().hex[:16]}"
        task = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            user_id=user_id,
            input_summary=input_summary[:100]  # 限制长度
        )
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息"""
        return self._tasks.get(task_id)

    def update_task_progress(self, task_id: str, progress: int):
        """更新任务进度"""
        if task_id in self._tasks:
            self._tasks[task_id].progress = min(100, max(0, progress))

    def _run_sync_in_executor(self, fn, *args, **kwargs):
        """在线程池中运行同步函数"""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(self._executor, fn, *args, **kwargs)

    async def execute_task(
        self,
        task_id: str,
        workflow_func: Callable,
        *args,
        **kwargs
    ):
        """
        执行任务
        :param task_id: 任务ID
        :param workflow_func: 工作流函数（同步）
        :param args: 位置参数
        :param kwargs: 关键字参数
        """
        task = self._tasks.get(task_id)
        if not task:
            print(f"[TaskManager] 任务 {task_id} 不存在")
            return

        # 更新状态为处理中
        task.status = TaskStatus.PROCESSING
        task.started_at = time.time()
        task.progress = 10

        try:
            # 在线程池中执行同步工作流
            task.progress = 30
            result = await self._run_sync_in_executor(workflow_func, *args, **kwargs)
            task.progress = 90

            # 处理结果
            if isinstance(result, dict):
                task.result = result
            else:
                task.result = {"output": str(result)}

            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.progress = 100

            print(f"[TaskManager] 任务 {task_id} 完成，耗时 {task._get_elapsed_time()}s")

        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
            task.error = "任务处理超时"
            task.completed_at = time.time()
            print(f"[TaskManager] 任务 {task_id} 超时")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            print(f"[TaskManager] 任务 {task_id} 失败: {e}")

    def get_user_tasks(self, user_id: int, limit: int = 20) -> list:
        """获取用户的任务列表"""
        user_tasks = [
            task for task in self._tasks.values()
            if task.user_id == user_id
        ]
        # 按创建时间倒序
        user_tasks.sort(key=lambda x: x.created_at, reverse=True)
        return [task.to_dict() for task in user_tasks[:limit]]

    def cancel_task(self, task_id: str) -> bool:
        """取消任务（仅可取消等待中的任务）"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.FAILED
            task.error = "任务已取消"
            task.completed_at = time.time()
            return True

        return False


# 全局任务管理器实例
task_manager = AsyncTaskManager()
