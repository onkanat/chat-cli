from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COMMAND_EXECUTOR_PATH = ROOT / "lib" / "command_executor.py"


def _load_command_executor_module():
    spec = importlib.util.spec_from_file_location(
        "command_executor_docs_generator",
        COMMAND_EXECUTOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to create command_executor import spec")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _render_command_sections(mod) -> str:
    sections = mod.get_command_doc_sections()
    titles = mod.COMMAND_DOC_SECTION_TITLES

    blocks: list[str] = []
    for section_key in ("model", "analytics", "system"):
        entries = sections.get(section_key, [])
        if not entries:
            continue

        lines = [f"### {titles[section_key]}", "", "```bash"]
        for entry in entries:
            lines.append(f"{entry.usage:<32} # {entry.description}")
        lines.append("```")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _render_readme_summary(mod) -> str:
    lines = [
        "## 🧭 Built-in Slash Commands",
        "",
        "The command catalog below is generated from `lib/command_executor.py`.",
        "Use in-app `/help` to verify live behavior in the REPL.",
        "",
        "```text",
    ]
    for entry in mod.COMMAND_HELP_CATALOG:
        lines.append(f"{entry.usage} - {entry.description}")
    lines.append("```")
    return "\n".join(lines)


def _replace_marker_block(text: str, marker_name: str, replacement: str) -> str:
    begin = f"<!-- BEGIN GENERATED: {marker_name} -->"
    end = f"<!-- END GENERATED: {marker_name} -->"

    if begin not in text or end not in text:
        raise RuntimeError(f"Missing marker block: {marker_name}")

    start_idx = text.index(begin) + len(begin)
    end_idx = text.index(end)
    return text[:start_idx] + "\n" + replacement + "\n" + text[end_idx:]


def main() -> None:
    mod = _load_command_executor_module()

    command_sections = _render_command_sections(mod)
    readme_summary = _render_readme_summary(mod)

    replacements = {
        ROOT / "README.md": {
            "slash-command-summary": readme_summary,
        },
        ROOT / "docs" / "FULL_README.md": {
            "repl-command-sections": command_sections,
        },
        ROOT / "docs" / "ARCHITECTURE.md": {
            "repl-command-sections": command_sections,
        },
    }

    for path, marker_map in replacements.items():
        original = path.read_text(encoding="utf-8")
        updated = original
        for marker_name, replacement in marker_map.items():
            updated = _replace_marker_block(updated, marker_name, replacement)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            print(f"Updated {path.relative_to(ROOT)}")
        else:
            print(f"No changes for {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
