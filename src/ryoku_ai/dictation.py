"""Integração com o ditado Omarchy (start/stop/cancel) — sem áudio nos logs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 20


class DictationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _which(name: str) -> str | None:
    return shutil.which(name)


def _run(
    argv: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            check=check,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "LANG": os.environ.get("LANG", "C.UTF-8")},
        )
    except FileNotFoundError as exc:
        raise DictationError("command_missing", f"Comando não encontrado: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise DictationError("timeout", f"Timeout ao executar {' '.join(argv[:3])}") from exc


def selected_backend() -> str:
    binary = _which("omarchy-default-dictation") or _which("omarchy")
    if binary and Path(binary).name == "omarchy-default-dictation":
        completed = _run([binary])
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:200]
            raise DictationError("backend_error", detail or "Falha ao ler backend de ditado.")
        return (completed.stdout or "").strip() or "unknown"
    if _which("omarchy"):
        completed = _run(["omarchy", "default", "dictation"])
        if completed.returncode == 0 and (completed.stdout or "").strip():
            return completed.stdout.strip()
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "omarchy/defaults/dictation"
    if config.is_file():
        return config.read_text(encoding="utf-8").strip() or "unknown"
    raise DictationError("backend_missing", "Nenhum backend de ditado Omarchy configurado.")


def _parse_json(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _superwhisper_status() -> dict[str, Any]:
    if not _which("superwhisper"):
        raise DictationError("superwhisper_missing", "superwhisper não está no PATH.")
    completed = _run(["superwhisper", "status"])
    data = _parse_json(completed.stdout)
    if not isinstance(data, dict):
        raise DictationError("status_invalid", "Resposta de status do Superwhisper inválida.")
    # Nunca espelhar transcrições / last.result em logs do Ryoku.
    sanitized = {
        "ready": bool(data.get("ready")),
        "phase": str(data.get("phase") or "unknown"),
        "recording_seconds": data.get("recording_seconds"),
        "session_id": data.get("session_id"),
        "asr_backend": None,
        "cloud": None,
    }
    workers = data.get("workers") if isinstance(data.get("workers"), dict) else {}
    asr = workers.get("asr") if isinstance(workers.get("asr"), dict) else {}
    backend = workers.get("asr_backend") or asr.get("backend")
    sanitized["asr_backend"] = backend
    sanitized["cloud"] = str(backend).lower() == "cloud"
    return sanitized


def _superwhisper_models_cloud() -> dict[str, Any]:
    if not _which("superwhisper"):
        return {"cloud": None, "offline_models_installed": None, "processing_hint": None}
    completed = _run(["superwhisper", "models", "show"])
    data = _parse_json(completed.stdout)
    if not isinstance(data, dict):
        return {"cloud": None, "offline_models_installed": None, "processing_hint": None}
    models = data.get("models") if isinstance(data.get("models"), list) else []
    installed = [
        m.get("id")
        for m in models
        if isinstance(m, dict) and isinstance(m.get("download"), dict) and m["download"].get("state") == "installed"
    ]
    # active mode is often null on free cloud tier; infer from status workers instead.
    return {
        "offline_models_installed": bool(installed),
        "installed_model_ids": installed,
        "license_state": (data.get("license") or {}).get("state") if isinstance(data.get("license"), dict) else None,
        "credentials_source": (data.get("credentials") or {}).get("source")
        if isinstance(data.get("credentials"), dict)
        else None,
    }


def _cancel_support(backend: str) -> dict[str, Any]:
    if backend == "superwhisper" and _which("superwhisper"):
        # Verificado no notebook: `superwhisper cancel` existe e devolve JSON {ok, cancelled, phase}.
        # omarchy-dictation NÃO expõe cancel público.
        return {
            "available": True,
            "method": "superwhisper_cli",
            "argv": ["superwhisper", "cancel"],
            "omarchy_public_cancel": False,
            "note": "Cancelamento programático via Superwhisper CLI, não via `omarchy dictation`.",
        }
    return {
        "available": False,
        "method": None,
        "argv": None,
        "omarchy_public_cancel": False,
        "note": (
            f"Backend `{backend}` sem cancel programático verificado. "
            "Não anunciar × como funcional até haver comando oficial."
        ),
    }


def capabilities() -> dict[str, Any]:
    omarchy = bool(_which("omarchy-dictation") or _which("omarchy"))
    backend = "unknown"
    backend_error = None
    try:
        backend = selected_backend()
    except DictationError as exc:
        backend_error = {"code": exc.code, "message": exc.message}

    cancel = _cancel_support(backend)
    status: dict[str, Any] | None = None
    models: dict[str, Any] = {}
    if backend == "superwhisper":
        try:
            status = _superwhisper_status()
        except DictationError as exc:
            status = {"error": {"code": exc.code, "message": exc.message}}
        models = _superwhisper_models_cloud()

    cloud = None
    if isinstance(status, dict) and status.get("cloud") is not None:
        cloud = bool(status.get("cloud"))

    return {
        "ok": backend_error is None and omarchy,
        "omarchy_dictation": omarchy,
        "backend": backend,
        "backend_error": backend_error,
        "commands": {
            "start": ["omarchy", "dictation", "start"],
            "stop": ["omarchy", "dictation", "stop"],
            "toggle": ["omarchy", "dictation", "toggle"],
            # omarchy não tem cancel; expomos o adaptador Ryoku.
            "cancel": ["ryoku", "dictation", "cancel"],
        },
        "cancel": cancel,
        "partial_transcript": False,
        "partial_transcript_note": (
            "Superwhisper `status --bar` só expõe fase/ícone; não há API pública de "
            "transcrição parcial para apps externos. UI deve mostrar Gravando…/Transcrevendo… "
            "sem legendas simuladas."
        ),
        "text_injection": "focused_field",
        "text_injection_note": (
            "Com autoPaste/textCommit do Superwhisper, o texto vai ao campo com foco "
            "no stop — o painel deve focar o composer antes do start."
        ),
        "processing": {
            "cloud": cloud,
            "asr_backend": (status or {}).get("asr_backend") if isinstance(status, dict) else None,
            "offline_models_installed": models.get("offline_models_installed"),
            "credentials_source": models.get("credentials_source"),
            "privacy_warning_pt": (
                "O backend Superwhisper neste notebook está em modo nuvem (ASR cloud). "
                "O áudio pode ser enviado ao provedor do Superwhisper. "
                "Modelos offline não estão instalados. Confirme antes de gravar."
                if cloud
                else (
                    "Modo de processamento aparentemente local/offline (ou indeterminado). "
                    "Confirme em `superwhisper models show` se precisar de garantia."
                )
            ),
        },
        "status": status,
        "siwc_not_used": True,
    }


def start() -> dict[str, Any]:
    if not (_which("omarchy-dictation") or _which("omarchy")):
        raise DictationError("omarchy_missing", "omarchy dictation não está disponível.")
    argv = ["omarchy", "dictation", "start"] if _which("omarchy") else ["omarchy-dictation", "start"]
    completed = _run(argv)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:240]
        raise DictationError("start_failed", detail or "Falha ao iniciar ditado.")
    return {"ok": True, "action": "start", "phase": "recording"}


def stop() -> dict[str, Any]:
    argv = ["omarchy", "dictation", "stop"] if _which("omarchy") else ["omarchy-dictation", "stop"]
    completed = _run(argv)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:240]
        raise DictationError("stop_failed", detail or "Falha ao parar ditado.")
    return {"ok": True, "action": "stop", "phase": "transcribing"}


def cancel() -> dict[str, Any]:
    caps = capabilities()
    support = caps.get("cancel") or {}
    if not support.get("available"):
        raise DictationError(
            "cancel_unavailable",
            str(support.get("note") or "Cancelamento programático indisponível neste backend."),
        )
    argv = list(support.get("argv") or [])
    if not argv:
        raise DictationError("cancel_unavailable", "Comando de cancelamento não configurado.")
    completed = _run(argv)
    payload = _parse_json(completed.stdout) or {}
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:240]
        raise DictationError("cancel_failed", detail or "Falha ao cancelar ditado.")
    # Resposta tipicamente {"cancelled": bool, "ok": bool, "phase": "idle"} — sem texto.
    return {
        "ok": bool(payload.get("ok", True)),
        "action": "cancel",
        "cancelled": bool(payload.get("cancelled", True)),
        "phase": str(payload.get("phase") or "idle"),
    }


def status() -> dict[str, Any]:
    caps = capabilities()
    backend = caps.get("backend")
    out: dict[str, Any] = {
        "ok": True,
        "backend": backend,
        "phase": "unknown",
        "recording": False,
        "ready": None,
        "cloud": (caps.get("processing") or {}).get("cloud"),
        "cancel_available": bool((caps.get("cancel") or {}).get("available")),
        "partial_transcript": False,
    }
    if backend == "superwhisper":
        try:
            st = _superwhisper_status()
        except DictationError as exc:
            raise DictationError(exc.code, exc.message) from exc
        phase = str(st.get("phase") or "unknown")
        out.update(
            {
                "phase": phase,
                "recording": phase in {"recording", "listening", "starting"},
                "transcribing": phase in {"processing", "transcribing", "finishing", "stopping"},
                "ready": st.get("ready"),
                "cloud": st.get("cloud"),
                "recording_seconds": st.get("recording_seconds"),
            }
        )
    return out
