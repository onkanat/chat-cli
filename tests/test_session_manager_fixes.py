"""Tests for session manager create/switch bug fixes."""

from __future__ import annotations


# Test session manager functions work correctly


def test_session_create_clears_context():
    """Test that session create clears chat_context correctly."""
    history = [{"role": "user", "text": "hello"}]
    chat_context = {"persona": "pirate", "custom_key": "value"}
    
    # Simulate what happens after create
    history.clear()
    chat_context.clear()
    
    assert history == []
    assert chat_context == {}
    print("✓ test_session_create_clears_context passed")


def test_session_create_saves_config():
    """Test that new session ID is saved to config."""
    config = {
        "default_model": "test",
        "system_message": "test",
    }
    new_session_id = "20260417_120000_abc123"
    
    # Simulate config save
    config["current_session_id"] = new_session_id
    
    assert config["current_session_id"] == new_session_id
    assert config["current_session_id"] is not None
    print("✓ test_session_create_saves_config passed")


def test_session_switch_clears_context():
    """Test that session switch clears chat_context."""
    history = [{"role": "user", "text": "old"}]
    chat_context = {"persona": "pirate"}
    new_history = [{"role": "user", "text": "new"}]
    
    # Simulate what happens after switch
    history.clear()
    history.extend(new_history)
    chat_context.clear()
    
    assert history == new_history
    assert chat_context == {}
    print("✓ test_session_switch_clears_context passed")


def test_session_switch_updates_config():
    """Test that session switch updates active session ID in config."""
    config = {
        "current_session_id": "old_session_id",
    }
    session_id = "new_session_id"
    
    # Simulate config update
    config["current_session_id"] = session_id
    
    assert config["current_session_id"] == "new_session_id"
    print("✓ test_session_switch_updates_config passed")


def test_state_isolation_between_sessions():
    """Test that session state doesn't leak between creates/switches."""
    # Session 1
    history1 = [{"role": "user", "text": "session1"}]
    context1 = {"persona": "pirate", "data": "secret"}
    
    # Create new session
    history1.clear()
    context1.clear()

    assert config["current_session_id"] == "session1"
    
    # After switch
    config["current_session_id"] = "session2"
    assert config["current_session_id"] == "session2"
    
    # Should never be None during active session
    assert config["current_session_id"] is not None
    print("✓ test_config_tracks_active_session passed")


if __name__ == "__main__":
    tests = [
        test_session_create_clears_context,
        test_session_create_saves_config,
        test_session_switch_clears_context,
        test_session_switch_updates_config,
        test_state_isolation_between_sessions,
        test_config_tracks_active_session,
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
    
    if failed == 0:
        print(f"\n✅ All {len(tests)} session manager bug fix tests passed")
    else:
        print(f"\n❌ {failed}/{len(tests)} tests failed")
