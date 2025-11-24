from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

SESSIONS_DIR = Path("histories")


def ensure_sessions_dir() -> None:
    """Create sessions directory if it doesn't exist."""
    SESSIONS_DIR.mkdir(exist_ok=True)


def save_history(
    history: List[Dict[str, Any]], path: Path | str = Path("chat_history.json")
) -> None:
    """Save history to JSON file.
    
    Args:
        history: List of history items to save
        path: Path to save file (default: chat_history.json)
    """
    path = Path(path)
    try:
        payload = json.dumps(history, ensure_ascii=False, indent=2)
        path.write_text(payload, encoding="utf-8")
    except Exception:
        pass


def load_history(path: Path | str = Path("chat_history.json")) -> List[Dict[str, Any]]:
    """Load history from JSON file.
    
    Args:
        path: Path to history file (default: chat_history.json)
        
    Returns:
        List of history items, empty list if file doesn't exist
    """
    path = Path(path)
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        return data
    except Exception:
        return []


def create_session(
    history: List[Dict[str, Any]],
    custom_name: Optional[str] = None,
    model_used: Optional[str] = None,
    persona: Optional[str] = None,
) -> str:
    """Create a new session and save current history.
    
    Args:
        history: Current conversation history
        custom_name: Optional custom name for the session
        model_used: Optional model name used in this session
        persona: Optional persona identifier
        
    Returns:
        Session ID (timestamp-based)
    """
    ensure_sessions_dir()

    # Generate session ID from timestamp
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create session metadata
    session_data = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "custom_name": custom_name,
        "model_used": model_used,
        "persona": persona,
        "message_count": len(history),
        "history": history,
    }

    # Save session file
    session_file = SESSIONS_DIR / f"{session_id}.json"
    try:
        payload = json.dumps(session_data, ensure_ascii=False, indent=2)
        session_file.write_text(payload, encoding="utf-8")
    except Exception:
        pass

    return session_id


def list_sessions() -> List[Dict[str, Any]]:
    """List all available sessions.
    
    Returns:
        List of session metadata (without full history)
    """
    ensure_sessions_dir()

    sessions = []
    for session_file in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            content = session_file.read_text(encoding="utf-8")
            data = json.loads(content)
            # Return metadata only, not full history
            session_info = {
                "session_id": data.get("session_id", session_file.stem),
                "created_at": data.get("created_at", ""),
                "custom_name": data.get("custom_name"),
                "model_used": data.get("model_used"),
                "persona": data.get("persona"),
                "message_count": data.get("message_count", 0),
            }
            sessions.append(session_info)
        except Exception:
            continue

    return sessions


def load_session(session_id: str) -> List[Dict[str, Any]]:
    """Load history from a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        History list, or empty list if session not found
    """
    ensure_sessions_dir()

    session_file = SESSIONS_DIR / f"{session_id}.json"
    if not session_file.exists():
        return []

    try:
        content = session_file.read_text(encoding="utf-8")
        data = json.loads(content)
        return data.get("history", [])
    except Exception:
        return []


def delete_session(session_id: str) -> bool:
    """Delete a session file.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if deleted successfully, False otherwise
    """
    ensure_sessions_dir()

    session_file = SESSIONS_DIR / f"{session_id}.json"
    if not session_file.exists():
        return False

    try:
        session_file.unlink()
        return True
    except Exception:
        return False
