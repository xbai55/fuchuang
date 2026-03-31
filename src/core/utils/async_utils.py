"""
Async utilities for running CPU-bound tasks.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, TypeVar

T = TypeVar('T')

# Global thread pool for CPU-bound tasks
_global_executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=4)


async def run_in_threadpool(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Run a synchronous function in the thread pool.

    Args:
        func: Synchronous function to run
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Function result
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _global_executor,
        lambda: func(*args, **kwargs)
    )


def asyncio_timeout(seconds: float):
    """
    Decorator to add timeout to async functions.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=seconds
            )
        return wrapper
    return decorator


class AsyncTaskGroup:
    """
    Helper class to manage a group of async tasks.
    """

    def __init__(self):
        self.tasks = []

    def add(self, coro):
        """Add a coroutine to the group."""
        self.tasks.append(asyncio.create_task(coro))

    async def gather(self, return_exceptions: bool = True):
        """Gather all tasks and return results."""
        if not self.tasks:
            return []
        return await asyncio.gather(*self.tasks, return_exceptions=return_exceptions)

    async def cancel_all(self):
        """Cancel all pending tasks."""
        for task in self.tasks:
            if not task.done():
                task.cancel()


def get_global_executor() -> ThreadPoolExecutor:
    """Get the global thread pool executor."""
    return _global_executor
