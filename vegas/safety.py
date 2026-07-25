"""
Safety confirmation layer for VEGAS AIOS.

Provides the @requires_confirmation decorator which intercepts tool execution,
parks the call in a pending-approval queue, and only runs it when the user
explicitly confirms via confirm_task().
"""

import functools
import inspect
import threading
from typing import Any, Callable, Dict, Tuple

from vegas.memory import add_task, update_task_status

_lock = threading.Lock()
# In-memory registry of deferred callables, keyed by task_id.
# Each entry stores (original_fn, args, kwargs).
_pending_actions: Dict[str, Tuple[Callable, tuple, dict]] = {}


def get_pending_action(task_id: str) -> Tuple[Callable, tuple, dict] | None:
    """Returns the deferred callable + arguments for a pending task, or None."""
    with _lock:
        return _pending_actions.get(task_id)


def pop_pending_action(task_id: str) -> Tuple[Callable, tuple, dict] | None:
    """Removes and returns the deferred callable for a pending task."""
    with _lock:
        return _pending_actions.pop(task_id, None)


def requires_confirmation(fn: Callable) -> Callable:
    """
    Decorator that intercepts a tool call, stores it for later approval,
    and returns a confirmation prompt instead of executing immediately.

    The original function only runs when the user calls confirm_task(<id>).
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        # Build a human-readable summary of what was requested.
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        arg_parts = [f"{k}={v!r}" for k, v in bound.arguments.items()]
        description = f"{fn.__name__}({', '.join(arg_parts)})"

        # Park the action in the pending queue.
        task_id = add_task(description)
        update_task_status(task_id, "awaiting_confirmation")
        _pending_actions[task_id] = (fn.__wrapped__ if hasattr(fn, "__wrapped__") else fn, args, kwargs)

        return (
            f"⚠️  VEGAS: This action requires your confirmation — {description}. "
            f"Say 'confirm task {task_id}' to proceed or 'cancel task {task_id}' to discard."
        )

    # Preserve the original function reference so confirm_task can call the
    # *unwrapped* version without re-triggering the decorator.
    wrapper._vegas_original = fn
    return wrapper
