"""Ryoku terminal commands. No shell execution and no API requests."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import __version__
from .diagnostics import collect, pretty


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="ryoku",
        description="緑 Ryoku AI — assistente de terminal para Omarchy (pré-alpha)",
    )
    root.add_argument("--version", action="version", version=f"ryoku-ai {__version__}")
    subs = root.add_subparsers(dest="command")
    doctor = subs.add_parser("doctor", help="diagnóstico local somente leitura")
    doctor.add_argument("--json", action="store_true", help="saída JSON sem dados pessoais")
    subs.add_parser("status", help="ver o estágio do projeto")
    subs.add_parser("chat", help="futuro chat com login oficial ChatGPT")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        print(f"緑 RYOKU AI v{__version__}")
        print("Assistente de terminal para Omarchy / Arch Linux")
        print("Comandos: ryoku doctor | ryoku status | ryoku chat")
        return 0
    if args.command == "doctor":
        report = collect()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(pretty(report))
        return 0
    if args.command == "status":
        print("緑 Ryoku AI — pré-alpha v0.1")
        print("CLI e diagnóstico local: prontos.")
        print("Login Sign in with ChatGPT e conversa: ainda não implementados.")
        print("Painel Quickshell: etapa futura.")
        print("Sem uso de tokens Codex, login copiado ou API com cobrança.")
        return 0
    if args.command == "chat":
        print(
            "Ryoku AI ainda não está conectado ao ChatGPT.\n"
            "Esta versão não faz login, não usa tokens do Codex nem consome seu Plus.\n"
            "O Cursor implementará o fluxo oficial Sign in with ChatGPT.\n"
            "Veja docs/AUTH.md e docs/CURSOR_TASKS.md.",
            file=sys.stderr,
        )
        return 3
    return 2


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
