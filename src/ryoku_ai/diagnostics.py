"""Deliberately non-identifying, read-only environment inspection."""

from __future__ import annotations

import platform
import shutil
from pathlib import Path

from .siwc import bridge_ready

TOOLS = ("omarchy", "omarchy-shell", "hyprctl", "quickshell", "git", "python3", "xdg-open", "node", "npm")


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
    siwc_ok, siwc_detail = bridge_ready()
    return {
        "platform": platform.system(),
        "distribution": distro,
        "arch_family": distro == "arch" or "arch" in family,
        "omarchy_cli": tools["omarchy"],
        "tools": tools,
        "siwc_bridge_ready": siwc_ok,
        "siwc_bridge_detail": siwc_detail,
        # Never claim PASS_REAL from doctor alone.
        "chatgpt_connection": "bridge_ready" if siwc_ok else "bridge_unavailable",
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
        f"Bridge SIWC: {'pronto' if report.get('siwc_bridge_ready') else 'indisponível'} ({report.get('siwc_bridge_detail')})",
        "ChatGPT: use ryoku login / ryoku status (PASS_REAL só após teste no notebook).",
        "Privacidade: não lê tokens, histórico, IPs, nomes ou arquivos pessoais.",
    ])
