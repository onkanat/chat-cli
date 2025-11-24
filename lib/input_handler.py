"""Enhanced input handler with command history and arrow key navigation."""

from __future__ import annotations

import readline
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
        """Add command to history."""
        if not command.strip():
            return
        # Remove duplicates of consecutive commands
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
    """Configure readline for arrow key navigation."""

    # Load history from file if it exists
    try:
        readline.read_history_file("chat_history.txt")
        # Convert readline history to our format
        for i in range(readline.get_current_history_length()):
            item = readline.get_history_item(i + 1)  # readline is 1-indexed
            if item:
                history.add(item.strip())
    except Exception:
        pass


def enhanced_input(prompt: str, history: CommandHistory) -> str:
    """Get input with enhanced history navigation."""

    try:
        # Use readline for better input handling
        import readline

        line = input(prompt)

        # Add to history if not empty
        if line.strip():
            history.add(line.strip())

        # Save history to file
        try:
            # Update readline history
            readline.add_history(line)
            readline.write_history_file("chat_history.txt")
        except Exception:
            pass

        return line

    except (EOFError, KeyboardInterrupt):
        return ""
    except Exception:
        return input(prompt)  # Fallback to basic input


def get_multiline_input(prompt: str, continuation_prompt: str = ">>> ") -> str:
    """Get multi-line input with Shift+Enter support."""
    lines = []

    try:
        # First line
        line = input(prompt)
        if line.strip():  # Only add non-empty lines
            lines.append(line)

        # Continue reading until empty line or Ctrl+D
        while True:
            try:
                line = input(continuation_prompt)
                if line.strip() == "" and len(lines) > 1:
                    # Empty line ends multi-line input
                    break
                if line.strip():  # Only add non-empty lines
                    lines.append(line)
            except EOFError:
                # Ctrl+D ends input
                break

    except (EOFError, KeyboardInterrupt):
        return ""

    # Join lines with newlines
    result = "\n".join(lines).strip()

    # Show line count if multi-line
    if len(lines) > 1:
        print(f"[dim]📝 Sent {len(lines)} lines[/dim]")

    return result


def enhanced_input_multiline(prompt: str, history: CommandHistory) -> str:
    """Enhanced input with multi-line support and history."""

    try:
        # Get first line
        line = input(prompt)

        # If line ends with \, it's multi-line mode
        if line.rstrip().endswith("\\"):
            # Remove the \ and start multi-line mode
            base_line = line.rstrip()[:-1]  # Remove trailing \
            lines = [base_line]

            print("[dim]💡 Multi-line mode: Enter continues, empty line submits[/dim]")

            while True:
                try:
                    continuation = input(">>> ")
                    if continuation.strip() == "" and len(lines) > 1:
                        # Empty line ends multi-line input
                        break
                    if continuation.strip():  # Only add non-empty lines
                        lines.append(continuation)
                except EOFError:
                    # Ctrl+D ends input
                    break

            result = "\n".join(lines).strip()
            if len(lines) > 1:
                print(f"[dim]📝 Sent {len(lines)} lines[/dim]")
        else:
            # Single line mode
            result = line

        # Add to history if not empty
        if result.strip():
            history.add(result.strip())

        # Update readline history
        try:
            import readline

            readline.add_history(result)
            readline.write_history_file("chat_history.txt")
        except Exception:
            pass

        return result

    except (EOFError, KeyboardInterrupt):
        return ""
    except Exception:
        # Fallback to basic input
        try:
            line = input(prompt)
            if line.strip():
                history.add(line.strip())
            return line
        except (EOFError, KeyboardInterrupt):
            return ""
    except Exception:
        # Fallback to basic input
        try:
            line = input(prompt)
            if line.strip():
                history.add(line.strip())
            return line
        except (EOFError, KeyboardInterrupt):
            return ""
    except Exception:
        # Fallback to basic input
        try:
            line = input(prompt)
            if line.strip():
                history.add(line.strip())
            return line
        except (EOFError, KeyboardInterrupt):
            return ""


def save_history_to_file(history: CommandHistory) -> None:
    """Save command history to file."""
    try:
        with open("chat_history.txt", "w") as f:
            for cmd in history.history:
                f.write(f"{cmd}\n")
    except Exception:
        pass
