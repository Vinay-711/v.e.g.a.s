import pytest
import re
from vegas.memory import _get_conn, set_preference, get_preference
from vegas.safety import requires_confirmation, _pending_actions
from vegas.tools.memory import confirm_task, cancel_task

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
    
    confirmation_result = confirm_task(task_id)
    assert "confirmed and executed" in confirmation_result
    assert "destroyed target" in confirmation_result
    
def test_cancel_task():
    @requires_confirmation
    def dangerous_function(arg1):
        return f"destroyed {arg1}"
    result = dangerous_function("target")
    task_id = re.search(r"confirm task ([a-f0-9\-]+)", result).group(1)
    
    cancellation_result = cancel_task(task_id)
    assert "cancelled" in cancellation_result
    assert task_id not in _pending_actions


