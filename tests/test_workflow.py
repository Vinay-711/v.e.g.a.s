import pytest
import re
from unittest.mock import MagicMock, patch
from vegas.safety import _pending_actions
from vegas.tools.memory import confirm_task, cancel_task
from vegas.tools.workflow import list_todays_events, draft_email, morning_briefing

@pytest.fixture(autouse=True)
def setup_safety_state():
    _pending_actions.clear()
    yield
    _pending_actions.clear()

@patch("vegas.tools.workflow._build_service")
def test_list_todays_events_success(mock_build):
    # Setup mock calendar service response
    mock_service = MagicMock()
    mock_events_list = mock_service.events.return_value.list.return_value
    mock_events_list.execute.return_value = {
        "items": [
            {
                "start": {"dateTime": "2026-07-17T09:00:00+05:30"},
                "summary": "Morning Sync"
            },
            {
                "start": {"dateTime": "2026-07-17T14:30:00+05:30"},
                "summary": "Design Review"
            }
        ]
    }
    mock_build.return_value = mock_service

    result = list_todays_events()
    assert "You have 2 event(s) remaining today" in result
    assert "09:00 AM — Morning Sync" in result
    assert "02:30 PM — Design Review" in result

@patch("vegas.tools.workflow._build_service")
def test_draft_email_flow(mock_build):
    # Setup mock gmail service response
    mock_service = MagicMock()
    mock_drafts_create = mock_service.users.return_value.drafts.return_value.create.return_value
    mock_drafts_create.execute.return_value = {"id": "mock_draft_999"}
    mock_build.return_value = mock_service

    # Call gated draft_email function
    result = draft_email(to="boss@starkark.com", subject="Vegas", body="System Active")
    
    # Must be intercepted by @requires_confirmation
    assert "VEGAS: This action requires your confirmation" in result
    task_id = re.search(r"confirm task ([a-f0-9\-]+)", result).group(1)
    assert task_id in _pending_actions

    # Execute confirmation
    confirm_result = confirm_task(task_id)
    assert "Gmail draft created successfully" in confirm_result
    assert "mock_draft_999" in confirm_result

@patch("vegas.tools.workflow._build_service")
def test_draft_email_cancellation(mock_build):
    # Setup mock gmail service response
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    # Call gated draft_email function
    result = draft_email(to="boss@starkark.com", subject="Vegas", body="System Active")
    task_id = re.search(r"confirm task ([a-f0-9\-]+)", result).group(1)
    
    # Execute cancellation
    cancel_result = cancel_task(task_id)
    assert "cancelled" in cancel_result
    assert task_id not in _pending_actions

@patch("vegas.tools.workflow.list_todays_events")
@patch("vegas.tools.web.open_world_monitor")
@patch("vegas.tools.memory.whats_pending")
def test_morning_briefing_aggregation(mock_whats_pending, mock_open_world_monitor, mock_list_todays_events):
    mock_list_todays_events.return_value = "• 09:00 AM — Morning Sync"
    mock_open_world_monitor.return_value = "=== SECTION 1 ===\nGlobal tech stocks up\n=== SECTION 2 ===\nGemini 2.5 Flash released"
    mock_whats_pending.return_value = "No pending actions."

    result = morning_briefing()
    assert "Good morning! Here's your daily briefing" in result
    assert "• 09:00 AM — Morning Sync" in result
    assert "Global tech stocks up" in result
    assert "No pending actions." in result
