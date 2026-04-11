from __future__ import annotations

import copy
import os
from pathlib import Path
from urllib.parse import urlparse

import ui as ui_mod
from services.server_profiles import (
    DEFAULT_SERVER_CONFIG,
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_REMOTE_BASE_URL,
)

DEFAULT_CONFIG = Path("config.json")


def _ensure_server_profiles(config: dict | None) -> dict:
    """Ensure server profile defaults exist without overwriting user data."""
    cfg = config.copy() if config else {}
    servers = cfg.get("ollama_servers")
    if not isinstance(servers, dict):
        cfg["ollama_servers"] = copy.deepcopy(DEFAULT_SERVER_CONFIG)
        return cfg

    profiles = servers.get("profiles")
    if not isinstance(profiles, dict):
        servers["profiles"] = copy.deepcopy(DEFAULT_SERVER_CONFIG["profiles"])
    else:
        profiles.setdefault(
            "local",
            {
                "label": "Localhost",
                "base_url": DEFAULT_LOCAL_BASE_URL,
            },
        )
        profiles.setdefault(
            "remote",
            {
                "label": "LAN Server",
                "base_url": DEFAULT_REMOTE_BASE_URL,
            },
        )

    active = servers.get("active")
    if not isinstance(active, str) or active not in servers["profiles"]:
        servers["active"] = DEFAULT_SERVER_CONFIG["active"]

    cfg["ollama_servers"] = servers
    return cfg


def _get_server_profiles(config: dict) -> tuple[dict, str]:
    cfg = _ensure_server_profiles(config)
    servers = cfg["ollama_servers"]
    return servers["profiles"], servers["active"]


def _set_active_server(config: dict, profile_name: str) -> dict:
    cfg = _ensure_server_profiles(config)
    servers = cfg["ollama_servers"]
    if profile_name in servers["profiles"]:
        servers["active"] = profile_name
    return cfg


def _set_server_base_url(
    config: dict, profile_name: str, base_url: str
) -> dict:
    cfg = _ensure_server_profiles(config)
    servers = cfg["ollama_servers"]
    profiles = servers["profiles"]
    profile = profiles.setdefault(
        profile_name,
        {
            "label": profile_name.title(),
            "base_url": base_url,
        },
    )
    profile["base_url"] = base_url
    return cfg


def _validate_base_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _determine_base_url(config: dict, cli_override: str | None) -> str:
    if cli_override:
        return cli_override
    env_override = os.getenv("OLLAMA_BASE_URL")
    if env_override:
        return env_override
    profiles, active = _get_server_profiles(config)
    profile = profiles.get(active, {})
    return profile.get("base_url", DEFAULT_LOCAL_BASE_URL)


def _server_switch_menu(config: dict) -> dict:
    cfg = _ensure_server_profiles(config)
    profiles, active = _get_server_profiles(cfg)
    names = list(profiles.keys())
    ui_mod.console.print("\n[bold]Available server profiles:[/bold]")
    for idx, name in enumerate(names, 1):
        profile = profiles[name]
        marker = "👉" if name == active else "  "
        label = profile.get("label", name.title())
        base = profile.get("base_url", "")
        line_txt = (
            f"{marker} [cyan]{idx}[/cyan]."
            f" [white]{label}[/white] [dim]({base})[/dim]"
        )
        ui_mod.console.print(line_txt)
    choice = input("Select server (number) or Enter to cancel: ").strip()
    if not choice:
        return cfg
    try:
        idx = int(choice)
    except ValueError:
        ui_mod.console.print("[red]❌ Invalid selection[/red]")
        return cfg
    if not 1 <= idx <= len(names):
        ui_mod.console.print("[red]❌ Selection out of range[/red]")
        return cfg
    selected = names[idx - 1]
    if selected == active:
        ui_mod.console.print("[yellow]ℹ️  Already active[/yellow]")
        return cfg
    cfg = _set_active_server(cfg, selected)
    profile = profiles[selected]
    ui_mod.console.print(
        "[green]✓ Active server set to:[/green] "
        f"[white]{profile.get('label', selected.title())}[/white]"
    )
    return cfg


def _server_edit_prompt(config: dict, profile_name: str) -> dict:
    cfg = _ensure_server_profiles(config)
    profiles, _ = _get_server_profiles(cfg)
    profile = profiles.get(profile_name, {})
    label = profile.get("label", profile_name.title())
    default_url = (
        DEFAULT_REMOTE_BASE_URL
        if profile_name == "remote"
        else DEFAULT_LOCAL_BASE_URL
    )
    current_url = profile.get("base_url", default_url)
    ui_mod.console.print(
        f"\n[bold]Editing {label} server[/bold]"
        f"\n[dim]Current URL:[/dim] [white]{current_url}[/white]"
    )
    new_url = input("Enter new base URL (or leave blank to cancel): ").strip()
    if not new_url:
        ui_mod.console.print("[yellow]⚠️  Update cancelled[/yellow]")
        return cfg
    if not _validate_base_url(new_url):
        ui_mod.console.print(
            "[red]❌ Invalid URL. Use http(s)://host:port[/red]"
        )
        return cfg
    cfg = _set_server_base_url(cfg, profile_name, new_url)
    ui_mod.console.print(
        f"[green]✓ {label} URL updated to:[/green] [white]{new_url}[/white]"
    )
    return cfg


def server_settings_menu(config: dict) -> dict:
    cfg = _ensure_server_profiles(config)
    while True:
        profiles, active = _get_server_profiles(cfg)
        active_profile = profiles.get(active, {})
        active_label = active_profile.get("label", active.title())
        active_url = active_profile.get("base_url", DEFAULT_LOCAL_BASE_URL)
        ui_mod.console.print(
            "\n[bold blue]🌐 Ollama Server Settings[/bold blue]"
        )
        ui_mod.console.print(
            "[dim]Active Server:[/dim] "
            f"[green]{active_label}[/green] [white]{active_url}[/white]"
        )
        ui_mod.console.print("\n[bold]Options:[/bold]")
        ui_mod.console.print("1. Switch active server")
        ui_mod.console.print("2. Edit local server URL")
        ui_mod.console.print("3. Edit remote server URL")
        ui_mod.console.print("4. Back to settings")
        try:
            choice = input("\nSelect option (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            ui_mod.console.print(
                "\n[yellow]⚠️  Server settings cancelled[/yellow]"
            )
            return cfg
        if choice == "1":
            cfg = _server_switch_menu(cfg)
        elif choice == "2":
            cfg = _server_edit_prompt(cfg, "local")
        elif choice == "3":
            cfg = _server_edit_prompt(cfg, "remote")
        elif choice == "4":
            return cfg
        else:
            ui_mod.console.print("[red]❌ Invalid option[/red]")


def settings_menu(config: dict) -> dict:
    """Interactive settings menu for model parameters."""
    ui_mod.console.print("\n[bold blue]⚙️  Settings Menu[/bold blue]")

    # Current settings
    current_temp = config.get("temperature", 0.7)
    current_max_tokens = config.get("max_tokens", 2048)
    current_theme = config.get("theme", "default")
    current_system_message = config.get("system_message", "")
    current_route = config.get("generation_route", "omni")
    fallback_enabled = bool(config.get("fallback_to_direct_on_error", True))
    current_omni_base = config.get("omni_base_url", "http://localhost:8000")
    current_omni_top_k = config.get("omni_top_k", 5)
    current_direct_ctx_cap = config.get("direct_num_ctx_cap", 4096)
    current_direct_fallback = config.get(
        "direct_memory_fallback_model",
        "gemma3:latest",
    )
    chat_prefer_direct = bool(config.get("chat_interface_prefer_direct", True))

    ui_mod.console.print(
        "[dim]Current Temperature:[/dim] "
        f"[cyan]{current_temp}[/cyan] (0.0-2.0)"
    )
    ui_mod.console.print(
        "[dim]Current Max Tokens:[/dim] "
        f"[cyan]{current_max_tokens}[/cyan] (100-16384)"
    )
    ui_mod.console.print(
        "[dim]Current Theme:[/dim] "
        f"[cyan]{current_theme}[/cyan] (default/dark/light)"
    )
    ui_mod.console.print(
        "[dim]Generation Route:[/dim] "
        f"[cyan]{current_route}[/cyan] (omni/auto/direct)"
    )
    ui_mod.console.print(
        "[dim]Fallback to Direct on Error:[/dim] "
        f"[cyan]{'on' if fallback_enabled else 'off'}[/cyan]"
    )
    ui_mod.console.print(
        "[dim]Omni Base URL:[/dim] "
        f"[cyan]{current_omni_base}[/cyan]"
    )
    ui_mod.console.print(
        "[dim]Omni top_k:[/dim] "
        f"[cyan]{current_omni_top_k}[/cyan] (1-20)"
    )
    ui_mod.console.print(
        "[dim]Direct num_ctx cap:[/dim] "
        f"[cyan]{current_direct_ctx_cap}[/cyan] (512-32768)"
    )
    ui_mod.console.print(
        "[dim]Direct OOM fallback model:[/dim] "
        f"[cyan]{current_direct_fallback}[/cyan]"
    )
    ui_mod.console.print(
        "[dim]Chat interface direct preference:[/dim] "
        f"[cyan]{'on' if chat_prefer_direct else 'off'}[/cyan]"
    )
    if current_system_message:
        display_msg = (
            current_system_message[:50] + "..."
            if len(current_system_message) > 50
            else current_system_message
        )
        ui_mod.console.print(
            f"[dim]Current System Message:[/dim] [cyan]{display_msg}[/cyan]"
        )
    else:
        ui_mod.console.print(
            "[dim]Current System Message:[/dim] [yellow]Not set[/yellow]"
        )

    ui_mod.console.print("\n[bold]Options:[/bold]")
    ui_mod.console.print("1. Change temperature")
    ui_mod.console.print("2. Change max tokens")
    ui_mod.console.print("3. Change theme")
    ui_mod.console.print("4. Change system message")
    ui_mod.console.print("5. Reset to defaults")
    ui_mod.console.print("6. Configure Ollama server")
    ui_mod.console.print("7. Change generation route")
    ui_mod.console.print("8. Toggle direct fallback on error")
    ui_mod.console.print("9. Change Omni base URL")
    ui_mod.console.print("10. Change Omni top_k")
    ui_mod.console.print("11. Change direct num_ctx cap")
    ui_mod.console.print("12. Change direct OOM fallback model")
    ui_mod.console.print("13. Toggle chat direct preference")
    ui_mod.console.print("14. Back to chat")

    try:
        choice = input("\nSelect option (1-14): ").strip()

        if choice == "1":
            try:
                new_temp = float(
                    input(
                        f"Enter temperature (0.0-2.0)"
                        f" [current: {current_temp}]: "
                    ).strip()
                    or str(current_temp)
                )
                if 0.0 <= new_temp <= 2.0:
                    config["temperature"] = new_temp
                    ui_mod.console.print(
                        f"[green]✓ Temperature set to:[/green]"
                        f" [white]{new_temp}[/white]"
                    )
                else:
                    ui_mod.console.print(
                        "[red]❌ Temperature must be between 0.0 and 2.0[/red]"
                    )
            except ValueError:
                ui_mod.console.print("[red]❌ Invalid temperature value[/red]")

        elif choice == "2":
            try:
                new_tokens = int(
                    input(
                        f"Enter max tokens (100-16384)"
                        f" [current: {current_max_tokens}]: "
                    ).strip()
                    or str(current_max_tokens)
                )
                if 100 <= new_tokens <= 16384:
                    config["max_tokens"] = new_tokens
                    ui_mod.console.print(
                        f"[green]✓ Max tokens set to:[/green]"
                        f" [white]{new_tokens}[/white]"
                    )
                else:
                    ui_mod.console.print(
                        "[red]❌ Max tokens must be between 100 and 16384[/red]"
                    )
            except ValueError:
                ui_mod.console.print("[red]❌ Invalid token value[/red]")

        elif choice == "3":
            # Change theme
            themes = ["default", "dark", "light"]
            current_theme = config.get("theme", "default")
            ui_mod.console.print("\n[bold]Available Themes:[/bold]")
            for i, theme in enumerate(themes, 1):
                marker = "👉" if theme == current_theme else "  "
                ui_mod.console.print(
                    f"{marker} [cyan]{i}[/cyan]. [white]{theme}[/white]"
                )

            try:
                theme_choice = input(
                    f"Select theme (1-{len(themes)})"
                    f" [current: {current_theme}]: "
                ).strip()
                if not theme_choice:
                    theme_choice = str(themes.index(current_theme) + 1)

                theme_num = int(theme_choice)
                if 1 <= theme_num <= len(themes):
                    selected_theme = themes[theme_num - 1]
                    config["theme"] = selected_theme
                    ui_mod.console.print(
                        f"[green]✓ Theme set to:[/green]"
                        f" [white]{selected_theme}[/white]"
                    )
                else:
                    ui_mod.console.print(
                        "[red]❌ Invalid theme selection[/red]"
                    )
            except ValueError:
                ui_mod.console.print("[red]❌ Invalid theme value[/red]")

        elif choice == "4":
            # System message configuration
            ui_mod.console.print(
                "\n[bold]System Message Configuration:[/bold]"
            )
            ui_mod.console.print("1. Edit system message")
            ui_mod.console.print("2. Use predefined template")
            ui_mod.console.print("3. Clear system message")
            ui_mod.console.print("4. Back to settings")

            try:
                sub_choice = input("\nSelect option (1-4): ").strip()

                if sub_choice == "1":
                    # Edit system message
                    ui_mod.console.print(
                        "\n[dim]Current system message:[/dim]"
                    )
                    if current_system_message:
                        ui_mod.console.print(
                            f"[cyan]{current_system_message}[/cyan]"
                        )
                    else:
                        ui_mod.console.print(
                            "[yellow]No system message set[/yellow]"
                        )

                    ui_mod.console.print(
                        "\n[dim]Enter new system message "
                        "(press Enter on empty line to finish):[/dim]"
                    )
                    lines = []
                    while True:
                        try:
                            line = input()
                            if line == "" and not lines:
                                break
                            if line == "" and lines:
                                break
                            lines.append(line)
                        except (KeyboardInterrupt, EOFError):
                            break

                    if lines:
                        new_system_message = "\n".join(lines)
                        config["system_message"] = new_system_message
                        ui_mod.console.print(
                            "[green]✓ System message updated[/green]"
                        )
                    else:
                        ui_mod.console.print(
                            "[yellow]⚠️  System message unchanged[/yellow]"
                        )

                elif sub_choice == "2":
                    # Predefined templates
                    templates = {
                        "1": (
                            "Sen hızlı ve akıcı düşünen "
                            "mühendislik araçlarını "
                            "iyi kullanan bir modelsin"
                        ),
                        "2": (
                            "Sen yardımcı ve bilgilendirici bir yapay zeka "
                            "asistanısın. Kullanıcıya en iyi şekilde yardımcı "
                            "olmaya çalış."
                        ),
                        "3": (
                            "Sen uzman bir programcısın. Kod yazma, hata "
                            "ayıklama ve optimizasyon konularında yardımcı ol."
                        ),
                        "4": (
                            "Sen analitik bir düşünecisin. "
                            "Sorunları mantıksal adımlarla çöz "
                            "ve açıklamalarını net yap."
                        ),
                    }

                    ui_mod.console.print(
                        "\n[bold]Predefined System Message Templates:[/bold]"
                    )
                    ui_mod.console.print("1. Engineering Assistant")
                    ui_mod.console.print("2. General Assistant")
                    ui_mod.console.print("3. Code Assistant")
                    ui_mod.console.print("4. Analytical Thinker")

                    try:
                        template_choice = input(
                            "\nSelect template (1-4): "
                        ).strip()
                        if template_choice in templates:
                            config["system_message"] = (
                                templates[template_choice]
                            )
                            ui_mod.console.print(
                                "[green]✓ System message"
                                " template applied[/green]"
                            )
                        else:
                            ui_mod.console.print(
                                "[red]❌ Invalid template selection[/red]"
                            )
                    except (ValueError, KeyboardInterrupt, EOFError):
                        ui_mod.console.print(
                            "[yellow]⚠️  Template selection cancelled[/yellow]"
                        )

                elif sub_choice == "3":
                    # Clear system message
                    config["system_message"] = ""
                    ui_mod.console.print(
                        "[green]✓ System message cleared[/green]"
                    )

                elif sub_choice == "4":
                    # Back to settings
                    pass

                else:
                    ui_mod.console.print("[red]❌ Invalid option[/red]")

            except (KeyboardInterrupt, EOFError):
                ui_mod.console.print(
                    "\n[yellow]⚠️  System message "
                    "configuration cancelled[/yellow]"
                )

        elif choice == "5":
            config["temperature"] = 0.7
            config["max_tokens"] = 2048
            config["theme"] = "default"
            config["system_message"] = (
                "Sen hızlı ve akıcı düşünen mühendislik "
                "araçlarını iyi kullanan bir modelsin"
            )
            config["generation_route"] = "omni"
            config["fallback_to_direct_on_error"] = True
            config["omni_base_url"] = "http://localhost:8000"
            config["omni_top_k"] = 5
            config["direct_num_ctx_cap"] = 4096
            config["direct_memory_fallback_model"] = "gemma3:latest"
            config["chat_interface_prefer_direct"] = True
            ui_mod.console.print("[green]✓ Settings reset to defaults[/green]")

        elif choice == "6":
            config = server_settings_menu(config)

        elif choice == "7":
            routes = ["omni", "auto", "direct"]
            route_now = str(config.get("generation_route", "omni")).lower()
            if route_now not in routes:
                route_now = "omni"

            ui_mod.console.print("\n[bold]Generation Route:[/bold]")
            ui_mod.console.print(
                "[dim]omni:[/dim] always use Omni-Daemon"
            )
            ui_mod.console.print(
                "[dim]auto:[/dim] try Omni-Daemon, then fallback direct"
            )
            ui_mod.console.print(
                "[dim]direct:[/dim] call Ollama directly"
            )

            for idx, route in enumerate(routes, 1):
                marker = "👉" if route == route_now else "  "
                ui_mod.console.print(
                    f"{marker} [cyan]{idx}[/cyan]. [white]{route}[/white]"
                )

            route_choice = input(
                f"Select route (1-{len(routes)}) [current: {route_now}]: "
            ).strip()
            if not route_choice:
                route_choice = str(routes.index(route_now) + 1)

            try:
                route_num = int(route_choice)
                if 1 <= route_num <= len(routes):
                    selected_route = routes[route_num - 1]
                    config["generation_route"] = selected_route
                    ui_mod.console.print(
                        "[green]✓ Generation route set to:[/green] "
                        f"[white]{selected_route}[/white]"
                    )
                else:
                    ui_mod.console.print(
                        "[red]❌ Invalid route selection[/red]"
                    )
            except ValueError:
                ui_mod.console.print("[red]❌ Invalid route value[/red]")

        elif choice == "8":
            current = bool(config.get("fallback_to_direct_on_error", True))
            config["fallback_to_direct_on_error"] = not current
            status = "on" if not current else "off"
            ui_mod.console.print(
                "[green]✓ Fallback to direct on error:[/green] "
                f"[white]{status}[/white]"
            )

        elif choice == "9":
            current = str(
                config.get("omni_base_url", "http://localhost:8000")
            ).strip()
            ui_mod.console.print("\n[bold]Omni Base URL[/bold]")
            ui_mod.console.print(f"[dim]Current:[/dim] [cyan]{current}[/cyan]")
            new_url = input(
                "Enter Omni base URL (or blank to cancel): "
            ).strip()
            if new_url:
                if _validate_base_url(new_url):
                    config["omni_base_url"] = new_url.rstrip("/")
                    ui_mod.console.print(
                        "[green]✓ Omni base URL set to:[/green] "
                        f"[white]{config['omni_base_url']}[/white]"
                    )
                else:
                    ui_mod.console.print("[red]❌ Invalid URL[/red]")
            else:
                ui_mod.console.print("[yellow]⚠️  Omni URL unchanged[/yellow]")

        elif choice == "10":
            current = config.get("omni_top_k", 5)
            try:
                value = int(
                    input(
                        f"Enter Omni top_k (1-20) [current: {current}]: "
                    ).strip()
                    or str(current)
                )
                if 1 <= value <= 20:
                    config["omni_top_k"] = value
                    ui_mod.console.print(
                        "[green]✓ Omni top_k set to:[/green] "
                        f"[white]{value}[/white]"
                    )
                else:
                    ui_mod.console.print(
                        "[red]❌ Omni top_k must be between 1 and 20[/red]"
                    )
            except ValueError:
                ui_mod.console.print("[red]❌ Invalid top_k value[/red]")

        elif choice == "11":
            current = config.get("direct_num_ctx_cap", 4096)
            try:
                value = int(
                    input(
                        "Enter direct num_ctx cap (512-32768) "
                        f"[current: {current}]: "
                    ).strip()
                    or str(current)
                )
                if 512 <= value <= 32768:
                    config["direct_num_ctx_cap"] = value
                    ui_mod.console.print(
                        "[green]✓ Direct num_ctx cap set to:[/green] "
                        f"[white]{value}[/white]"
                    )
                else:
                    ui_mod.console.print(
                        "[red]❌ direct num_ctx cap must be 512-32768[/red]"
                    )
            except ValueError:
                ui_mod.console.print("[red]❌ Invalid num_ctx value[/red]")

        elif choice == "12":
            current = str(
                config.get("direct_memory_fallback_model", "")
            ).strip()
            ui_mod.console.print("\n[bold]Direct OOM fallback model[/bold]")
            ui_mod.console.print(
                "[dim]Leave blank to disable model switch fallback[/dim]"
            )
            if current:
                ui_mod.console.print(
                    f"[dim]Current:[/dim] [cyan]{current}[/cyan]"
                )
            new_model = input(
                "Enter fallback model (e.g. gemma3:latest): "
            ).strip()
            config["direct_memory_fallback_model"] = new_model
            if new_model:
                ui_mod.console.print(
                    "[green]✓ Direct OOM fallback model set to:[/green] "
                    f"[white]{new_model}[/white]"
                )
            else:
                ui_mod.console.print(
                    "[yellow]⚠️  Direct OOM fallback model disabled[/yellow]"
                )

        elif choice == "13":
            current = bool(config.get("chat_interface_prefer_direct", True))
            config["chat_interface_prefer_direct"] = not current
            status = "on" if not current else "off"
            ui_mod.console.print(
                "[green]✓ Chat interface direct preference:[/green] "
                f"[white]{status}[/white]"
            )

        elif choice == "14":
            return config

        else:
            ui_mod.console.print("[red]❌ Invalid option[/red]")

    except (KeyboardInterrupt, EOFError):
        ui_mod.console.print("\n[yellow]⚠️  Settings cancelled[/yellow]")

    return config
