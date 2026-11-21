"""Ryoku terminal commands. Diagnóstico local + SIWC via bridge oficial."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .chat import run_chat_repl
from .diagnostics import collect, pretty
from .siwc import SiwcBridge, SiwcError, bridge_ready, default_storage_dir, format_session


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="ryoku",
        description="緑 Ryoku AI — assistente de terminal para Omarchy (pré-alpha)",
    )
    root.add_argument("--version", action="version", version=f"ryoku-ai {__version__}")
    subs = root.add_subparsers(dest="command")

    doctor = subs.add_parser("doctor", help="diagnóstico local somente leitura")
    doctor.add_argument("--json", action="store_true", help="saída JSON sem dados pessoais")

    status = subs.add_parser("status", help="estado do projeto e da sessão ChatGPT")
    status.add_argument("--json", action="store_true", help="saída JSON sem tokens")

    login = subs.add_parser("login", help="Sign in with ChatGPT (navegador + PKCE)")
    login.add_argument("--new-profile", action="store_true", help="registrar outra conta")
    login.add_argument("--profile-id", help="reatenticar um perfil salvo")
    login.add_argument(
        "--reconsent",
        action="store_true",
        help="solicitar novamente consentimento de uso do plano",
    )
    login.add_argument(
        "--storage-dir",
        type=Path,
        help="diretório absoluto de armazenamento (padrão: ~/.config/ryoku-ai-omarchy)",
    )

    logout = subs.add_parser("logout", help="remover credenciais locais do perfil ativo")
    logout.add_argument("--storage-dir", type=Path)

    models = subs.add_parser("models", help="listar modelos disponíveis após login")
    models.add_argument("--json", action="store_true")
    models.add_argument("--storage-dir", type=Path)

    chat = subs.add_parser("chat", help="conversa real via plano ChatGPT autorizado")
    chat.add_argument("-m", "--model", help="slug do modelo (padrão: primeiro disponível)")
    chat.add_argument("-p", "--prompt", help="mensagem única (sem REPL)")
    chat.add_argument("--storage-dir", type=Path)

    return root


def _bridge(storage_dir: Path | None) -> SiwcBridge:
    return SiwcBridge(storage_dir=storage_dir or default_storage_dir())


def _cmd_status(as_json: bool) -> int:
    ready, reason = bridge_ready()
    payload: dict[str, object] = {
        "version": __version__,
        "stage": "sprint1-siwc",
        "bridge_ready": ready,
        "bridge_detail": reason,
        "doctor": "ok",
        "quickshell": "not_implemented",
        "notes": [
            "Não usa tokens Codex/Cursor nem cookies do navegador.",
            "Não usa chave de API cobrada à parte.",
            "PASS_REAL do login ainda exige validação manual no notebook.",
        ],
    }
    if ready:
        try:
            with _bridge(None) as bridge:
                session = bridge.request("session")
                profiles = bridge.request("profiles")
            payload["session"] = session
            payload["profiles"] = profiles
        except SiwcError as exc:
            payload["session_error"] = {"code": exc.code, "message": exc.message}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"緑 Ryoku AI — pré-alpha v{__version__}")
    print("CLI e diagnóstico local: prontos.")
    print(f"Bridge SIWC: {'pronto' if ready else 'indisponível'} ({reason})")
    if "session" in payload and isinstance(payload["session"], dict):
        for line in format_session(payload["session"]):
            print(line)
    elif "session_error" in payload:
        err = payload["session_error"]
        assert isinstance(err, dict)
        print(f"Sessão: erro [{err.get('code')}] {err.get('message')}")
    else:
        print("Sessão ChatGPT: desconectada (bridge indisponível ou sem login).")
    print("Painel Quickshell: etapa futura.")
    print("Sem uso de tokens Codex, login copiado ou API com cobrança.")
    print("Login real no notebook ainda é necessário antes de declarar PASS_REAL.")
    return 0


def _cmd_login(args: argparse.Namespace) -> int:
    ready, reason = bridge_ready()
    if not ready:
        print(reason, file=sys.stderr)
        print("Veja docs/AUTH.md (empacotamento do @siwc/local).", file=sys.stderr)
        return 2
    try:
        with _bridge(args.storage_dir) as bridge:
            print("Abrindo o navegador para Sign in with ChatGPT…", file=sys.stderr)
            print("Conceda identidade e, se elegível, o uso do plano Plus/Pro.", file=sys.stderr)
            session = bridge.request(
                "login",
                {
                    "newProfile": bool(args.new_profile),
                    "reconsent": bool(args.reconsent),
                    **({"profileId": args.profile_id} if args.profile_id else {}),
                },
            )
    except SiwcError as exc:
        print(f"Falha no login [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1
    assert isinstance(session, dict)
    for line in format_session(session):
        print(line)
    if session.get("sharing"):
        print("Consentimento de uso do plano ativo. Próximo passo: ryoku models | ryoku chat")
    else:
        print(
            "Autenticado sem sharing. Se o plano for elegível, rode: ryoku login --reconsent",
            file=sys.stderr,
        )
    return 0


def _cmd_logout(args: argparse.Namespace) -> int:
    ready, reason = bridge_ready()
    if not ready:
        print(reason, file=sys.stderr)
        return 2
    try:
        with _bridge(args.storage_dir) as bridge:
            session = bridge.request("logout")
    except SiwcError as exc:
        print(f"Falha no logout [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1
    assert isinstance(session, dict)
    print("Credenciais locais do perfil ativo removidas.")
    for line in format_session(session):
        print(line)
    return 0


def _cmd_models(args: argparse.Namespace) -> int:
    ready, reason = bridge_ready()
    if not ready:
        print(reason, file=sys.stderr)
        return 2
    try:
        with _bridge(args.storage_dir) as bridge:
            session = bridge.request("session")
            if not isinstance(session, dict) or not session.get("sharing"):
                print(
                    "É necessário login com session.sharing=true antes de listar modelos.",
                    file=sys.stderr,
                )
                return 3
            models = bridge.request("models")
    except SiwcError as exc:
        print(f"Falha ao listar modelos [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(models, ensure_ascii=False, indent=2))
        return 0
    assert isinstance(models, list)
    if not models:
        print("Nenhum modelo retornado para este perfil.")
        return 0
    for item in models:
        if isinstance(item, dict):
            print(f"{item.get('slug')}\t{item.get('displayName')}")
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    ready, reason = bridge_ready()
    if not ready:
        print(reason, file=sys.stderr)
        print(
            "Ryoku AI ainda não pode conversar sem o bridge SIWC oficial.\n"
            "Não usa tokens do Codex nem chave de API cobrada à parte.\n"
            "Veja docs/AUTH.md.",
            file=sys.stderr,
        )
        return 3
    try:
        with _bridge(args.storage_dir) as bridge:
            return run_chat_repl(bridge, model=args.model, one_shot=args.prompt)
    except SiwcError as exc:
        print(f"Chat indisponível [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        print(f"緑 RYOKU AI v{__version__}")
        print("Assistente de terminal para Omarchy / Arch Linux")
        print("Comandos: ryoku doctor | status | login | logout | models | chat")
        return 0
    if args.command == "doctor":
        report = collect()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(pretty(report))
        return 0
    if args.command == "status":
        return _cmd_status(bool(args.json))
    if args.command == "login":
        return _cmd_login(args)
    if args.command == "logout":
        return _cmd_logout(args)
    if args.command == "models":
        return _cmd_models(args)
    if args.command == "chat":
        return _cmd_chat(args)
    return 2


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
