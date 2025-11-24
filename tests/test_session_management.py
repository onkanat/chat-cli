"""Test session management functions."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

import lib.history as history_mod


TEST_SESSIONS_DIR = Path("test_histories")


@pytest.fixture(autouse=True)
def setup_test_sessions_dir(monkeypatch):
    """Setup temporary sessions directory for tests."""
    # Override the SESSIONS_DIR constant in session_manager module
    import lib.session_manager as session_manager
    monkeypatch.setattr(session_manager, "SESSIONS_DIR", TEST_SESSIONS_DIR)
    monkeypatch.setattr(history_mod, "SESSIONS_DIR", TEST_SESSIONS_DIR)
    
    # Clean up before test
    if TEST_SESSIONS_DIR.exists():
        shutil.rmtree(TEST_SESSIONS_DIR)
    
    yield
    
    # Clean up after test
    if TEST_SESSIONS_DIR.exists():
        shutil.rmtree(TEST_SESSIONS_DIR)


def test_create_new_session():
    """Test creating a new session."""
    test_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    
    session_id = history_mod.create_new_session(
        history=test_history,
        custom_name="Test Session",
        model_used="llama3.2",
        persona="engineer",
    )
    
    # Session ID should be timestamp format
    assert len(session_id) == 15  # YYYYMMDD_HHMMSS
    assert "_" in session_id
    
    # Session file should exist
    session_file = TEST_SESSIONS_DIR / f"{session_id}.json"
    assert session_file.exists()
    
    # Verify session content
    content = json.loads(session_file.read_text())
    assert content["session_id"] == session_id
    assert content["custom_name"] == "Test Session"
    assert content["model_used"] == "llama3.2"
    assert content["persona"] == "engineer"
    assert content["message_count"] == 2
    assert len(content["history"]) == 2
    assert content["history"][0]["role"] == "user"


def test_list_sessions():
    """Test listing all sessions."""
    # Create multiple sessions
    history1 = [{"role": "user", "content": "First"}]
    history2 = [{"role": "user", "content": "Second"}]
    
    session_id1 = history_mod.create_new_session(
        history=history1,
        custom_name="Session One",
        model_used="llama3.2",
    )
    
    # Small delay to ensure different timestamps
    time.sleep(1.1)
    
    session_id2 = history_mod.create_new_session(
        history=history2,
        custom_name="Session Two",
        model_used="deepseek-r1:8b",
    )
    
    # List sessions
    sessions = history_mod.list_sessions()
    
    assert len(sessions) == 2
    
    # Should be sorted by session_id descending (newest first)
    assert sessions[0]["session_id"] == session_id2
    assert sessions[1]["session_id"] == session_id1
    
    # Check metadata (should not include full history)
    assert "history" not in sessions[0]
    assert sessions[0]["custom_name"] == "Session Two"
    assert sessions[0]["model_used"] == "deepseek-r1:8b"
    assert sessions[0]["message_count"] == 1


def test_load_session():
    """Test loading a specific session."""
    test_history = [
        {"role": "user", "content": "Test message"},
        {"role": "assistant", "content": "Test response"},
    ]
    
    session_id = history_mod.create_new_session(
        history=test_history,
        custom_name="Load Test",
    )
    
    # Load the session
    loaded_history = history_mod.load_session(session_id)
    
    assert len(loaded_history) == 2
    assert loaded_history[0]["role"] == "user"
    assert loaded_history[0]["content"] == "Test message"
    assert loaded_history[1]["role"] == "assistant"
    assert loaded_history[1]["content"] == "Test response"


def test_load_nonexistent_session():
    """Test loading a session that doesn't exist."""
    loaded_history = history_mod.load_session("nonexistent_20240101_000000")
    assert loaded_history == []


def test_delete_session():
    """Test deleting a session."""
    test_history = [{"role": "user", "content": "Delete me"}]
    
    session_id = history_mod.create_new_session(
        history=test_history,
        custom_name="To Delete",
    )
    
    # Session should exist
    session_file = TEST_SESSIONS_DIR / f"{session_id}.json"
    assert session_file.exists()
    
    # Delete it
    result = history_mod.delete_session(session_id)
    assert result is True
    assert not session_file.exists()
    
    # Try deleting again (should return False)
    result = history_mod.delete_session(session_id)
    assert result is False


def test_list_sessions_empty():
    """Test listing sessions when none exist."""
    sessions = history_mod.list_sessions()
    assert sessions == []


def test_create_session_creates_directory():
    """Test that creating a session creates the sessions directory."""
    assert not TEST_SESSIONS_DIR.exists()
    
    history_mod.create_new_session(
        history=[{"role": "user", "content": "Test"}],
    )
    
    assert TEST_SESSIONS_DIR.exists()
    assert TEST_SESSIONS_DIR.is_dir()
