"""Deliberately non-identifying, read-only environment inspection."""

from __future__ import annotations

import platform
import shutil
from pathlib import Path

TOOLS = ("omarchy", "omarchy-shell", "hyprctl", "quickshell", "git", "python3", "xdg-open")


def os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    result: dict[str, str] = {}
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"ID", "ID_LIKE"}:
            result[key] = value.strip().strip('"').strip("'")
    return result


def collect() -> dict[str, object]:
    release = os_release()
    distro = release.get("ID", "unknown")
    family = release.get("ID_LIKE", "").split()
    tools = {tool: shutil.which(tool) is not None for tool in TOOLS}
    return {
        "platform": platform.system(),
        "distribution": distro,
        "arch_family": distro == "arch" or "arch" in family,
        "omarchy_cli": tools["omarchy"],
        "tools": tools,
        "chatgpt_connection": "not_implemented",
    }


def pretty(report: dict[str, object]) -> str:
    tools = report["tools"]
    assert isinstance(tools, dict)
    return "\n".join([
        "緑 Ryoku AI — diagnóstico somente leitura",
        f"Sistema: {report['platform']} / {report['distribution']}",
        f"Família Arch: {'sim' if report['arch_family'] else 'não'}",
        f"Omarchy CLI: {'encontrado' if report['omarchy_cli'] else 'não encontrado'}",
        "Ferramentas: " + ", ".join(f"{name}={'ok' if found else 'ausente'}" for name, found in tools.items()),
        "ChatGPT: login e conversa ainda não implementados.",
        "Privacidade: não lê tokens, histórico, IPs, nomes ou arquivos pessoais.",
    ])
