from __future__ import annotations

DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/api"
DEFAULT_REMOTE_BASE_URL = "http://192.168.1.14:11434/api"

DEFAULT_SERVER_CONFIG = {
    "active": "local",
    "profiles": {
        "local": {
            "label": "Localhost",
            "base_url": DEFAULT_LOCAL_BASE_URL,
        },
        "remote": {
            "label": "LAN Server",
            "base_url": DEFAULT_REMOTE_BASE_URL,
        },
    },
}
