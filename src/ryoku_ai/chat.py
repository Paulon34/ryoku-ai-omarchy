"""Conversa com histórico local persistente e contexto reenviado ao modelo."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .attachments import (
    AttachmentError,
    ExtractedAttachment,
    extract_many,
    format_attachments_for_prompt,
)
from .history import (
    DEFAULT_CONTEXT_CHAR_BUDGET,
    HistoryStore,
    build_context_window,
    default_db_path,
    suggest_title,
)
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


def require_sharing_session(bridge: SiwcBridge) -> dict[str, Any]:
    session = bridge.request("session")
    if not isinstance(session, dict) or session.get("status") != "connected":
        raise SiwcError("sign_in_required", "Não há sessão conectada. Rode: ryoku login")
    if not session.get("sharing"):
        raise SiwcError(
            "sharing_not_enabled",
            "Sessão autenticada sem consentimento do plano (session.sharing=false). "
            "Rode: ryoku login --reconsent",
        )
    profile_id = session.get("profileId")
    if not isinstance(profile_id, str) or not profile_id:
        raise SiwcError("invalid_session", "Sessão sem profileId. Faça login novamente.")
    return session


def emit_jsonl(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def run_turn(
    bridge: SiwcBridge,
    store: HistoryStore,
    *,
    conversation_id: str,
    profile_id: str,
    model: str,
    user_text: str,
    attachments: Sequence[ExtractedAttachment] | None = None,
    on_delta: Callable[[str], None] | None = None,
    jsonl: bool = False,
) -> str:
    attached = list(attachments or [])
    composed = format_attachments_for_prompt(attached, user_text)
    prior = store.list_messages(conversation_id)
    # Reserva orçamento para o turno atual (anexos + pergunta).
    reserve = min(len(composed) + 1000, DEFAULT_CONTEXT_CHAR_BUDGET // 2)
    window = build_context_window(
        prior,
        budget=max(8_000, DEFAULT_CONTEXT_CHAR_BUDGET - reserve),
    )
    if window.truncated and not jsonl:
        sys.stderr.write(
            f"Aviso: contexto truncado — {window.omitted} mensagem(ns) antiga(s) "
            f"fora do orçamento de {window.budget} caracteres.\n"
        )
    for item in attached:
        if item.truncated or item.warning:
            note = item.warning or "truncado"
            if not jsonl:
                sys.stderr.write(f"Anexo {item.filename}: {note}\n")
    input_messages = [*window.messages, {"role": "user", "content": composed}]
    if jsonl:
        emit_jsonl(
            "start",
            conversation_id=conversation_id,
            model=model,
            truncated=window.truncated,
            omitted=window.omitted,
            attachments=[item.to_public_dict() for item in attached],
        )
    collected: list[str] = []

    def capture(delta: str) -> None:
        collected.append(delta)
        if jsonl:
            emit_jsonl("delta", text=delta)
        elif on_delta:
            on_delta(delta)

    display_user = user_text
    if attached:
        names = ", ".join(item.filename for item in attached)
        display_user = f"{user_text}\n\n[anexos: {names}]"

    try:
        text = bridge.chat_stream(model=model, input=input_messages, on_delta=capture)
    except KeyboardInterrupt:
        if jsonl:
            emit_jsonl("error", code="cancelled", message="Interrompido.", partial=bool(collected))
        raise
    except SiwcError as exc:
        partial = "".join(collected)
        if partial:
            store.append_turn(
                conversation_id,
                user_text=display_user,
                assistant_text=partial,
                status="partial",
                model=model,
                title_if_empty=suggest_title(user_text),
                profile_id=profile_id,
                attachments=attached,
            )
        if jsonl:
            emit_jsonl("error", code=exc.code, message=exc.message, retryable=exc.retryable)
        raise

    final = text or "".join(collected)
    store.append_turn(
        conversation_id,
        user_text=display_user,
        assistant_text=final,
        status="complete",
        model=model,
        title_if_empty=suggest_title(user_text),
        profile_id=profile_id,
        attachments=attached,
    )
    if jsonl:
        emit_jsonl("done", conversation_id=conversation_id, text=final)
    return final


def run_chat_repl(
    bridge: SiwcBridge,
    *,
    model: str | None = None,
    one_shot: str | None = None,
    attachment_paths: Sequence[str] | None = None,
    conversation_id: str | None = None,
    create_new: bool = False,
    jsonl: bool = False,
    history_path: Path | None = None,
    write: Callable[[str], None] | None = None,
    read_line: Callable[[], str] | None = None,
) -> int:
    out = write or (lambda text: print(text, end="", flush=True))
    readline = read_line or (lambda: sys.stdin.readline())

    try:
        session = require_sharing_session(bridge)
    except SiwcError as exc:
        if jsonl:
            emit_jsonl("error", code=exc.code, message=exc.message)
        else:
            out(f"{exc.message}\n")
        return 3

    profile_id = str(session["profileId"])
    try:
        selected = pick_model(bridge, model)
    except SiwcError as exc:
        if jsonl:
            emit_jsonl("error", code=exc.code, message=exc.message)
        else:
            out(f"{exc.message}\n")
        return 3

    store = HistoryStore(history_path or default_db_path())
    try:
        try:
            conv = store.resolve_conversation(
                profile_id,
                conversation_id=conversation_id,
                create_new=create_new,
                model=selected,
            )
        except KeyError as exc:
            out(f"{exc}\n")
            return 3

        if not jsonl:
            out(f"緑 Ryoku chat — modelo: {selected}\n")
            out(f"Conversa: {conv.id} — {conv.title}\n")
            out("Histórico local persistente. Ctrl+C ou linha vazia para sair.\n\n")

        def turn(prompt: str, paths: Sequence[str] | None = None) -> None:
            try:
                extracted = extract_many(list(paths or []))
            except AttachmentError as exc:
                if jsonl:
                    emit_jsonl("error", code=exc.code, message=exc.message)
                else:
                    out(f"Anexo: {exc.message}\n")
                raise
            if not jsonl:
                out("Ryoku: ")
            try:
                run_turn(
                    bridge,
                    store,
                    conversation_id=conv.id,
                    profile_id=profile_id,
                    model=selected,
                    user_text=prompt,
                    attachments=extracted,
                    on_delta=(None if jsonl else (lambda delta: out(delta))),
                    jsonl=jsonl,
                )
            except KeyboardInterrupt:
                if not jsonl:
                    out("\n[interrupção — histórico anterior preservado]\n")
                raise
            if not jsonl:
                out("\n\n")

        if one_shot is not None:
            try:
                turn(one_shot, attachment_paths)
            except AttachmentError:
                return 1
            except SiwcError as exc:
                if not jsonl:
                    out(f"\nErro [{exc.code}]: {exc.message}\n")
                return 1
            except KeyboardInterrupt:
                if not jsonl:
                    out("\n")
                return 130
            return 0

        while True:
            try:
                if not jsonl:
                    out("Você: ")
                line = readline()
                if line == "":
                    if not jsonl:
                        out("\n")
                    return 0
                prompt = line.rstrip("\n")
                if not prompt.strip():
                    if not jsonl:
                        out("Saindo.\n")
                    return 0
                turn(prompt, None)
            except AttachmentError:
                continue
            except SiwcError as exc:
                if not jsonl:
                    out(f"\nErro [{exc.code}]: {exc.message}\n")
                if exc.code in {"sign_in_required", "sharing_not_enabled", "invalid_grant"}:
                    return 3
                continue
            except KeyboardInterrupt:
                if not jsonl:
                    out("\nSaindo.\n")
                return 130
    finally:
        store.close()
