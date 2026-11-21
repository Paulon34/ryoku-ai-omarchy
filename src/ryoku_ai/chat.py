"""REPL de conversa via Responses API (plano ChatGPT autorizado)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from .siwc import SiwcBridge, SiwcError


def pick_model(bridge: SiwcBridge, requested: str | None) -> str:
    models = bridge.request("models")
    if not isinstance(models, list) or not models:
        raise SiwcError(
            "no_models",
            "Nenhum modelo disponível para este perfil. Verifique Plus/Pro e o consentimento do plano.",
        )
    if requested:
        for item in models:
            if isinstance(item, dict) and item.get("slug") == requested:
                return requested
        available = ", ".join(
            str(item.get("slug")) for item in models if isinstance(item, dict)
        )
        raise SiwcError("unknown_model", f"Modelo '{requested}' indisponível. Disponíveis: {available}")
    first = models[0]
    assert isinstance(first, dict)
    return str(first["slug"])


def run_chat_repl(
    bridge: SiwcBridge,
    *,
    model: str | None = None,
    one_shot: str | None = None,
    write: Callable[[str], None] | None = None,
    read_line: Callable[[], str] | None = None,
) -> int:
    out = write or (lambda text: print(text, end="", flush=True))
    readline = read_line or (lambda: sys.stdin.readline())

    session = bridge.request("session")
    if not isinstance(session, dict) or session.get("status") != "connected":
        out("Não há sessão conectada. Rode: ryoku login\n")
        return 3
    if not session.get("sharing"):
        out(
            "Sessão autenticada, mas sem consentimento de uso do plano (session.sharing=false).\n"
            "Rode: ryoku login --reconsent\n"
        )
        return 3

    try:
        selected = pick_model(bridge, model)
    except SiwcError as exc:
        out(f"{exc.message}\n")
        return 3

    out(f"緑 Ryoku chat — modelo: {selected}\n")
    out("Digite mensagens. Ctrl+C ou linha vazia para sair. Histórico não é salvo automaticamente.\n\n")

    def turn(prompt: str) -> None:
        out("Ryoku: ")
        try:
            bridge.chat_stream(
                model=selected,
                message=prompt,
                on_delta=lambda delta: out(delta),
            )
        except KeyboardInterrupt:
            out("\n[interrupção]\n")
            raise
        out("\n\n")

    if one_shot is not None:
        try:
            turn(one_shot)
        except SiwcError as exc:
            out(f"\nErro [{exc.code}]: {exc.message}\n")
            return 1
        except KeyboardInterrupt:
            out("\n")
            return 130
        return 0

    while True:
        try:
            out("Você: ")
            line = readline()
            if line == "":
                # EOF
                out("\n")
                return 0
            prompt = line.rstrip("\n")
            if not prompt.strip():
                out("Saindo.\n")
                return 0
            turn(prompt)
        except SiwcError as exc:
            out(f"\nErro [{exc.code}]: {exc.message}\n")
            if exc.code in {"sign_in_required", "sharing_not_enabled", "invalid_grant"}:
                return 3
            continue
        except KeyboardInterrupt:
            out("\nSaindo.\n")
            return 130
