import os
import pytest
import re
from pathlib import Path
from vegas.safety import _pending_actions
from vegas.tools.memory import confirm_task, cancel_task
from vegas.tools.files import (
    _verify_sandbox_path,
    read_file,
    write_file,
    delete_file,
    list_directory
)
from vegas.tools.browser import browse_and_extract, fill_web_form

@pytest.fixture(autouse=True)
def setup_safety_state():
    _pending_actions.clear()
    yield
    _pending_actions.clear()

def test_sandbox_path_validation():
    # Verify paths inside the sandbox root are resolved and allowed
    # (since VEGAS_SANDBOX_ROOT is set to the repository folder)
    allowed_path = _verify_sandbox_path("pyproject.toml")
    assert allowed_path.name == "pyproject.toml"

    # Verify escaping paths raise PermissionError
    with pytest.raises(PermissionError):
        _verify_sandbox_path("/etc/passwd")

    with pytest.raises(PermissionError):
        _verify_sandbox_path("../../../secret.txt")

def test_sandboxed_file_read_write_delete():
    target = "sandbox_test_file.txt"
    content = "Hello Vegas Sandbox"
    
    # 1. Gated write
    res_write = write_file(path=target, content=content)
    assert "VEGAS: This action requires your confirmation" in res_write
    task_id = re.search(r"confirm task ([a-f0-9\-]+)", res_write).group(1)
    
    # Confirm write
    confirm_res = confirm_task(task_id)
    assert "Successfully wrote to file" in confirm_res

    # 2. Read file (ungated)
    res_read = read_file(path=target)
    assert res_read == content

    # 3. List directory (ungated)
    res_list = list_directory(".")
    assert target in res_list

    # 4. Gated delete
    res_delete = delete_file(path=target)
    assert "VEGAS: This action requires your confirmation" in res_delete
    task_id_del = re.search(r"confirm task ([a-f0-9\-]+)", res_delete).group(1)

    # Confirm delete
    confirm_del_res = confirm_task(task_id_del)
    assert "Successfully deleted file" in confirm_del_res

    # Verify it is deleted
    assert not Path(target).exists()

def test_playwright_browse_extract():
    # Headless scraping of example.com
    res = browse_and_extract(url="https://example.com")
    assert "Example Domain" in res

def test_playwright_form_submission_gate():
    # Form submission with submit=True should trigger confirmation gate
    res = fill_web_form(url="https://example.com", field_values={"name": "Tony"}, submit=True)
    assert "VEGAS: This action requires your confirmation" in res
    task_id = re.search(r"confirm task ([a-f0-9\-]+)", res).group(1)
    assert task_id in _pending_actions
    
    cancel_res = cancel_task(task_id)
    assert "cancelled" in cancel_res
