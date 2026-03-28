"""Enhanced input handler with command history and arrow key navigation."""

from __future__ import annotations

import readline
from pathlib import Path
from typing import List, Optional

# Flag to indicate if enhanced input is available
INPUT_ENHANCED = True


class CommandHistory:
    """Manages command history with navigation."""

    def __init__(self, max_size: int = 20):
        self.history: List[str] = []
        self.max_size = max_size
        self.position = 0
        self.temp_input = ""

    def add(self, command: str) -> None:
        """Add command to history (avoid exact consecutive duplicates)."""
        if not command.strip():
            return
        if self.history and self.history[-1] == command:
            return
        self.history.append(command)
        if len(self.history) > self.max_size:
            self.history.pop(0)
        self.position = len(self.history)

    def get_up(self) -> Optional[str]:
        """Get previous command from history."""
        if self.position > 0:
            self.position -= 1
            return self.history[self.position]
        return None

    def get_down(self) -> Optional[str]:
        """Get next command from history."""
        if self.position < len(self.history) - 1:
            self.position += 1
            return self.history[self.position]
        return None

    def get_current(self) -> str:
        """Get current input."""
        return self.temp_input

    def set_current(self, text: str) -> None:
        """Set current input text."""
        self.temp_input = text
        self.position = len(self.history)


def setup_readline(history: CommandHistory) -> None:
    """
    Load persisted history from chat_history.txt into CommandHistory and readline.
    Avoid double-adding by using CommandHistory as the single source of truth.
    """
    try:
        path = Path("chat_history.txt")
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                history.add(line.strip())

        # Sync to readline_clear & populate with cleaned history
        try:
            readline.clear_history()
            for cmd in history.history:
                readline.add_history(cmd)
        except Exception:
            pass
    except Exception:
        pass


def enhanced_input(prompt: str, history: CommandHistory) -> str:
    """Get input with enhanced history navigation."""
    try:
        line = input(prompt)
        if line.strip():
            history.add(line.strip())
            # persist and sync centrally
            save_history_to_file(history)
        return line
    except (EOFError, KeyboardInterrupt):
        return ""
    except Exception:
        return input(prompt)  # Fallback to basic input


def get_multiline_input(prompt: str, continuation_prompt: str = ">>> ") -> str:
    """Get multi-line input with Shift+Enter support."""
    lines: List[str] = []
    try:
        line = input(prompt)
        if line.strip():
            lines.append(line)
        while True:
            try:
                line = input(continuation_prompt)
                if line.strip() == "" and len(lines) > 1:
                    break
                if line.strip():
                    lines.append(line)
            except EOFError:
                break
    except (EOFError, KeyboardInterrupt):
        return ""
    result = "\n".join(lines).strip()
    if len(lines) > 1:
        print(f"[dim]📝 Sent {len(lines)} lines[/dim]")
    return result


def enhanced_input_multiline(prompt: str, history: CommandHistory) -> str:
    """Enhanced input with multi-line support and history."""
    try:
        line = input(prompt)

        # Check for bulk paste (multiple lines arriving instantly)
        lines = [line]
        pasted = False
        try:
            import sys
            import select
            if sys.platform == 'win32':
                import msvcrt
                import time
                time.sleep(0.1)
                while msvcrt.kbhit():
                    lines.append(input())
                    pasted = True
                    time.sleep(0.1)
            else:
                while True:
                    # 0.15s timeout to correctly handle terminal chunked pastes
                    # (some terminals pause briefly when pasting large blocks >1024 bytes)
                    rlist, _, _ = select.select([sys.stdin], [], [], 0.15)
                    if rlist:
                        lines.append(input())
                        pasted = True
                    else:
                        break
        except Exception:
            pass

        if pasted:
            result = "\n".join(lines).strip()
            print(f"[dim]📝 Detected paste of {len(lines)} lines[/dim]")
        elif line.rstrip().endswith("\\"):
            base_line = line.rstrip()[:-1]
            lines = [base_line]
            print("[dim]💡 Multi-line mode: Enter continues, empty line submits[/dim]")
            while True:
                try:
                    continuation = input(">>> ")
                    if continuation.strip() == "" and len(lines) > 1:
                        break
                    if continuation.strip():
                        lines.append(continuation)
                except EOFError:
                    break
            result = "\n".join(lines).strip()
            if len(lines) > 1:
                print(f"[dim]📝 Sent {len(lines)} lines[/dim]")
        else:
            result = line

        if result.strip():
            history.add(result.strip())
            save_history_to_file(history)

        return result
    except (EOFError, KeyboardInterrupt):
        return ""
    except Exception:
        # final fallback
        try:
            line = input(prompt)
            if line.strip():
                history.add(line.strip())
                save_history_to_file(history)
            return line
        except (EOFError, KeyboardInterrupt):
            return ""


def save_history_to_file(history: CommandHistory) -> None:
    """Save command history to file and keep readline in sync."""
    try:
        path = Path("chat_history.txt")
        path.write_text("\n".join(history.history) + ("\n" if history.history else ""), encoding="utf-8")
    except Exception:
        pass

    try:
        readline.clear_history()
        for cmd in history.history:
            readline.add_history(cmd)
    except Exception:
        pass
