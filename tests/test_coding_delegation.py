import os
import pytest
from pathlib import Path
from vegas.tools.coding import dispatch_coding_task

@pytest.fixture
def cleanup_files():
    # Setup
    target_file = Path("test_delegated.txt")
    if target_file.exists():
        target_file.unlink()
    yield
    # Cleanup
    if target_file.exists():
        target_file.unlink()

def test_dispatch_coding_task_antigravity(cleanup_files):
    # Dispatch coding task to Antigravity
    repo_path = "."
    task = "Write a file named test_delegated.txt containing the exact string 'delegated success' and verify it exists"
    
    result = dispatch_coding_task(repo_path=repo_path, task_description=task, cli="antigravity")
    
    assert "completed successfully" in result
    assert "antigravity" in result
    
    # Assert the file is written
    target_file = Path("test_delegated.txt")
    assert target_file.exists()
    assert target_file.read_text().strip() == "delegated success"
