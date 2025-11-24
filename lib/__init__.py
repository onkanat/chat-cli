"""Core library modules - backward compatibility exports."""

# Re-export all modules for backward compatibility
from lib.config import *  # noqa: F401, F403
from lib.history import *  # noqa: F401, F403
from lib.ollama_wrapper import *  # noqa: F401, F403
from lib.input_handler import *  # noqa: F401, F403
from lib.message_builder import *  # noqa: F401, F403
from lib.session_manager import *  # noqa: F401, F403
from lib.shell_output import *  # noqa: F401, F403
from lib.plugin_registry import *  # noqa: F401, F403
from lib.plugins import *  # noqa: F401, F403
