"""Makes asyncio tolerate "nested" loop runs, which Qt programs do all the time.

Under qasync the asyncio loop runs inside Qt's event loop. Whenever a coroutine calls something that spins Qt's event loop
(`QApplication.processEvents()`, a modal `QDialog.exec()`, `QMessageBox`, ...), the other ready tasks are executed *inside* the step of
the task that is currently running. Python then refuses to start them:

    RuntimeError: Cannot enter into task <...> while another task <...> is being executed.

and the refused task never runs again - silently. In the logs of this program that hit the emotion detection, the dashboard, the web
server start and the network LLM loader. This module lets such a nested step simply run (the outer task is remembered and put back
afterwards), which is exactly what the nested event loop means.
"""
from __future__ import annotations

import asyncio
import asyncio.tasks as _tasks
import logging

logger = logging.getLogger("AsyncioNesting")
_stack: dict = {}
_installed = False


def _enter_task(loop, task):
    current = _tasks._current_tasks.get(loop)
    if current is not None and current is not task:
        _stack.setdefault(loop, []).append(current)         # a nested step inside another task's step
    _tasks._current_tasks[loop] = task


def _leave_task(loop, task):
    outer = _stack.get(loop)
    if outer:
        _tasks._current_tasks[loop] = outer.pop()
    else:
        _tasks._current_tasks.pop(loop, None)


def install(loop: asyncio.AbstractEventLoop) -> None:
    """Call once, right after the (qasync) loop was created."""
    global _installed
    try:
        if not _installed:
            _tasks._enter_task = _enter_task
            _tasks._leave_task = _leave_task
            _installed = True
        # the pure-Python Task looks the two functions above up when it runs a step; the C implementation would not
        loop.set_task_factory(lambda lp, coro, **kw: _tasks._PyTask(coro, loop=lp, **kw))
        logger.info("Nested task steps are tolerated (qasync / dialogs / processEvents)")
    except Exception:
        logger.exception("Could not install the nested-task patch")
