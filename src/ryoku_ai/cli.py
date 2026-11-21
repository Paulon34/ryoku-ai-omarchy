"""Ryoku terminal commands. Diagnóstico, SIWC e histórico local."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .chat import run_chat_repl
from .diagnostics import collect, pretty
from .history import HistoryStore, default_db_path
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

    chat = subs.add_parser("chat", help="conversa real com histórico local persistente")
    chat.add_argument("-m", "--model", help="slug do modelo (padrão: primeiro disponível)")
    chat.add_argument(
        "-p",
        "--prompt",
        help="mensagem única (CLI). Preferir --prompt-stdin na UI para não expor em ps",
    )
    chat.add_argument(
        "--prompt-stdin",
        action="store_true",
        help="ler a mensagem completa de stdin (recomendado para o painel Quickshell)",
    )
    chat.add_argument("--new", action="store_true", help="criar nova conversa")
    chat.add_argument("--conversation", help="retomar conversa pelo ID")
    chat.add_argument(
        "--jsonl",
        action="store_true",
        help="eventos NDJSON start/delta/done/error (para a UI)",
    )
    chat.add_argument("--storage-dir", type=Path)
    chat.add_argument("--history-db", type=Path, help="caminho do SQLite de conversas")

    history = subs.add_parser("history", help="gerenciar conversas locais")
    history_subs = history.add_subparsers(dest="history_command", required=True)

    h_list = history_subs.add_parser("list", help="listar conversas do perfil ativo")
    h_list.add_argument("--json", action="store_true")
    h_list.add_argument("--storage-dir", type=Path)
    h_list.add_argument("--history-db", type=Path)

    h_show = history_subs.add_parser("show", help="mostrar mensagens de uma conversa")
    h_show.add_argument("conversation_id")
    h_show.add_argument("--json", action="store_true")
    h_show.add_argument("--storage-dir", type=Path)
    h_show.add_argument("--history-db", type=Path)

    h_rename = history_subs.add_parser("rename", help="renomear conversa")
    h_rename.add_argument("conversation_id")
    h_rename.add_argument("title")
    h_rename.add_argument("--storage-dir", type=Path)
    h_rename.add_argument("--history-db", type=Path)

    h_delete = history_subs.add_parser("delete", help="apagar uma conversa (confirmação)")
    h_delete.add_argument("conversation_id")
    h_delete.add_argument("--yes", action="store_true", help="confirmar sem prompt interativo")
    h_delete.add_argument("--storage-dir", type=Path)
    h_delete.add_argument("--history-db", type=Path)

    h_clear = history_subs.add_parser("clear", help="apagar todas as conversas do perfil")
    h_clear.add_argument("--yes", action="store_true", help="confirmar sem prompt interativo")
    h_clear.add_argument("--storage-dir", type=Path)
    h_clear.add_argument("--history-db", type=Path)

    return root


def _bridge(storage_dir: Path | None) -> SiwcBridge:
    return SiwcBridge(storage_dir=storage_dir or default_storage_dir())


def _profile_id(bridge: SiwcBridge) -> str:
    session = bridge.request("session")
    if not isinstance(session, dict) or session.get("status") != "connected":
        raise SiwcError("sign_in_required", "Faça login para acessar o histórico do perfil.")
    profile_id = session.get("profileId")
    if not isinstance(profile_id, str) or not profile_id:
        raise SiwcError("invalid_session", "Sessão sem profileId.")
    return profile_id


def _confirm(prompt: str, *, assumed_yes: bool) -> bool:
    if assumed_yes:
        return True
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes", "s", "sim"}


def _cmd_status(as_json: bool) -> int:
    ready, reason = bridge_ready()
    payload: dict[str, object] = {
        "version": __version__,
        "stage": "sprint2-history-quickshell",
        "bridge_ready": ready,
        "bridge_detail": reason,
        "doctor": "ok",
        "history_db": str(default_db_path()),
        "quickshell_plugin": "io.github.paulon34.ryoku-ai",
        "notes": [
            "Não usa tokens Codex/Cursor nem cookies do navegador.",
            "Histórico local ≠ memória do ChatGPT.",
            "PASS_REAL do painel/histórico ainda exige validação no notebook.",
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
    print("CLI, diagnóstico e histórico local: prontos.")
    print(f"Bridge SIWC: {'pronto' if ready else 'indisponível'} ({reason})")
    print(f"Histórico SQLite: {default_db_path()}")
    if "session" in payload and isinstance(payload["session"], dict):
        for line in format_session(payload["session"]):
            print(line)
    elif "session_error" in payload:
        err = payload["session_error"]
        assert isinstance(err, dict)
        print(f"Sessão: erro [{err.get('code')}] {err.get('message')}")
    else:
        print("Sessão ChatGPT: desconectada (bridge indisponível ou sem login).")
    print("Plugin Quickshell: io.github.paulon34.ryoku-ai (instalar via scripts/install-plugin.sh).")
    print("Sem uso de tokens Codex, login copiado ou API com cobrança.")
    print("PASS_REAL no notebook ainda é necessário antes do merge.")
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
    print("Histórico local de conversas foi preservado (logout não apaga SQLite).")
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

    one_shot = args.prompt
    if args.prompt_stdin:
        one_shot = sys.stdin.read()
        if not one_shot.strip():
            print("stdin vazio.", file=sys.stderr)
            return 2

    try:
        with _bridge(args.storage_dir) as bridge:
            return run_chat_repl(
                bridge,
                model=args.model,
                one_shot=one_shot,
                conversation_id=args.conversation,
                create_new=bool(args.new),
                jsonl=bool(args.jsonl),
                history_path=args.history_db,
            )
    except SiwcError as exc:
        print(f"Chat indisponível [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1


def _cmd_history(args: argparse.Namespace) -> int:
    ready, reason = bridge_ready()
    if not ready:
        print(reason, file=sys.stderr)
        return 2
    db = args.history_db or default_db_path()
    try:
        with _bridge(args.storage_dir) as bridge:
            profile_id = _profile_id(bridge)
        store = HistoryStore(db)
    except SiwcError as exc:
        print(f"{exc.message}", file=sys.stderr)
        return 3

    try:
        if args.history_command == "list":
            items = [c.to_dict() for c in store.list_conversations(profile_id)]
            if args.json:
                print(json.dumps(items, ensure_ascii=False, indent=2))
            else:
                if not items:
                    print("Nenhuma conversa salva para este perfil.")
                for item in items:
                    print(
                        f"{item['id']}\t{item['updated_at']}\t"
                        f"{item['message_count']} msgs\t{item['title']}"
                    )
            return 0

        if args.history_command == "show":
            conv = store.get_conversation(args.conversation_id, profile_id)
            if conv is None:
                print("Conversa não encontrada para este perfil.", file=sys.stderr)
                return 3
            messages = [m.to_dict() for m in store.list_messages(conv.id)]
            payload = {"conversation": conv.to_dict(), "messages": messages}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"{conv.id} — {conv.title}")
                for message in messages:
                    print(f"[{message['role']}/{message['status']}] {message['content']}")
            return 0

        if args.history_command == "rename":
            try:
                conv = store.rename(args.conversation_id, profile_id, args.title)
            except (KeyError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 3
            print(f"Renomeada: {conv.id} → {conv.title}")
            return 0

        if args.history_command == "delete":
            if not _confirm(
                f"Apagar permanentemente a conversa {args.conversation_id}?",
                assumed_yes=bool(args.yes),
            ):
                print("Cancelado.")
                return 1
            try:
                store.delete(args.conversation_id, profile_id)
            except KeyError as exc:
                print(str(exc), file=sys.stderr)
                return 3
            print("Conversa apagada. (VACUUM/secure_delete aplicados; snapshots do SO podem restar.)")
            return 0

        if args.history_command == "clear":
            if not _confirm(
                "Apagar TODAS as conversas deste perfil? Irreversível no SQLite local.",
                assumed_yes=bool(args.yes),
            ):
                print("Cancelado.")
                return 1
            deleted = store.clear_profile(profile_id)
            print(f"{deleted} conversa(s) apagada(s).")
            return 0
    finally:
        store.close()
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        print(f"緑 RYOKU AI v{__version__}")
        print("Assistente de terminal para Omarchy / Arch Linux")
        print(
            "Comandos: ryoku doctor | status | login | logout | models | chat | history"
        )
        print("Dica: `ryoku chat` retoma a conversa mais recente; `ryoku chat --new` cria outra.")
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
    if args.command == "history":
        return _cmd_history(args)
    return 2


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
