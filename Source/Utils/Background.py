"""Fire-and-forget tasks a cog starts, such as refreshing a player's other messages.

asyncio keeps only a weak reference to a task, so one that nobody holds can be
garbage-collected mid-run. Background holds each task until it finishes, and
cancels whatever is still running when the cog unloads:

    self.background = Background()          # in __init__
    self.background.spawn(coro)
    self.background.cancel_all()            # in cog_unload
"""
import asyncio
from typing import Any, Coroutine, Set


class Background:
    def __init__(self) -> None:
        self._tasks: Set[asyncio.Task] = set()

    def __len__(self) -> int:
        return len(self._tasks)

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()
