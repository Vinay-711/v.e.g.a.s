import pytest
import re
from vegas.memory import _get_conn, set_preference, get_preference, update_task_status
from vegas.safety import requires_confirmation, pop_pending_action, _pending_actions

def confirm_task_local(task_id: str) -> str:
    entry = pop_pending_action(task_id)
    if entry is None:
        return f"No pending action found for task '{task_id}'."
    fn, args, kwargs = entry
    result = fn(*args, **kwargs)
    update_task_status(task_id, "completed", result=str(result))
    return f"confirmed and executed. Result: {result}"

def cancel_task_local(task_id: str) -> str:
    pop_pending_action(task_id)
    update_task_status(task_id, "cancelled")
    return f"has been cancelled"

@pytest.fixture(autouse=True)
def setup_db():
    conn = _get_conn()
    conn.execute("DELETE FROM preferences")
    conn.execute("DELETE FROM events")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    _pending_actions.clear()

def test_sqlite_memory_persists():
    set_preference("test_key", "test_value")
    assert get_preference("test_key") == "test_value"
    
def test_requires_confirmation_parks_task():
    @requires_confirmation
    def dangerous_function(arg1):
        return f"destroyed {arg1}"
    result = dangerous_function("target")
    assert "VEGAS: This action requires your confirmation" in result
    task_id = re.search(r"confirm task ([a-f0-9\-]+)", result).group(1)
    assert task_id in _pending_actions
    
def test_confirm_task_executes():
    @requires_confirmation
    def dangerous_function(arg1):
        return f"destroyed {arg1}"
    result = dangerous_function("target")
    task_id = re.search(r"confirm task ([a-f0-9\-]+)", result).group(1)
    
    confirmation_result = confirm_task_local(task_id)
    assert "confirmed and executed" in confirmation_result
    assert "destroyed target" in confirmation_result
    
def test_cancel_task():
    @requires_confirmation
    def dangerous_function(arg1):
        return f"destroyed {arg1}"
    result = dangerous_function("target")
    task_id = re.search(r"confirm task ([a-f0-9\-]+)", result).group(1)
    
    cancellation_result = cancel_task_local(task_id)
    assert "has been cancelled" in cancellation_result
    assert task_id not in _pending_actions

