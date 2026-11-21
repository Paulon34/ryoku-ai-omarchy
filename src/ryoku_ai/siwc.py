"""Cliente Python do bridge oficial @siwc/local (Sign in with ChatGPT)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_ID = "ryoku-ai-omarchy"
BRIDGE_REL = Path("siwc_bridge") / "src" / "bridge.mjs"


class SiwcError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class BridgePaths:
    repo_root: Path
    bridge_script: Path
    node_modules: Path

    @classmethod
    def discover(cls, start: Path | None = None) -> BridgePaths:
        here = (start or Path(__file__)).resolve()
        for candidate in [here, *here.parents]:
            script = candidate / BRIDGE_REL
            if script.is_file():
                return cls(
                    repo_root=candidate,
                    bridge_script=script,
                    node_modules=candidate / "siwc_bridge" / "node_modules",
                )
        raise SiwcError(
            "bridge_missing",
            "Bridge SIWC não encontrado. Execute npm install em siwc_bridge/ a partir da raiz do repositório.",
        )


def default_storage_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_ID


def node_binary() -> str | None:
    return shutil.which("node")


def bridge_ready(paths: BridgePaths | None = None) -> tuple[bool, str]:
    node = node_binary()
    if not node:
        return False, "Node.js 22+ não encontrado no PATH (necessário para @siwc/local)."
    try:
        completed = subprocess.run(
            [node, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError as exc:
        return False, f"Não foi possível executar Node.js: {exc}"
    version = (completed.stdout or completed.stderr or "").strip().lstrip("v")
    major = int(version.split(".", 1)[0]) if version and version[0].isdigit() else 0
    if major < 22:
        return False, f"Node.js {version or '?'} encontrado; @siwc/local exige Node >= 22."
    try:
        resolved = paths or BridgePaths.discover()
    except SiwcError as exc:
        return False, exc.message
    if not (resolved.node_modules / "@siwc" / "local").exists():
        return False, "Dependências do bridge ausentes. Rode: (cd siwc_bridge && npm install)"
    return True, "bridge pronto"


class SiwcBridge:
    """Processo Node de longa duração falando NDJSON."""

    def __init__(
        self,
        *,
        storage_dir: Path | None = None,
        test_memory_crypto: bool = False,
        paths: BridgePaths | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.paths = paths or BridgePaths.discover()
        self.storage_dir = (storage_dir or default_storage_dir()).resolve()
        self.test_memory_crypto = test_memory_crypto
        self._extra_env = dict(env or {})
        self._proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> SiwcBridge:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def start(self) -> None:
        if self._proc is not None:
            return
        ready, reason = bridge_ready(self.paths)
        if not ready:
            raise SiwcError("bridge_unavailable", reason)
        node = node_binary()
        assert node is not None
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.storage_dir, 0o700)
        env = os.environ.copy()
        env.update(self._extra_env)
        env["RYOKU_SIWC_STORAGE_DIR"] = str(self.storage_dir)
        if self.test_memory_crypto:
            env["RYOKU_SIWC_TEST_MEMORY_CRYPTO"] = "1"
        else:
            env.pop("RYOKU_SIWC_TEST_MEMORY_CRYPTO", None)
        self._proc = subprocess.Popen(
            [node, str(self.paths.bridge_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.paths.repo_root / "siwc_bridge"),
            env=env,
            bufsize=1,
        )

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is None:
                continue
            try:
                stream.close()
            except OSError:
                pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except OSError:
                pass


    def _ensure(self) -> subprocess.Popen[str]:
        if self._proc is None or self._proc.poll() is not None:
            self._proc = None
            self.start()
        assert self._proc is not None
        return self._proc

    def request(self, op: str, args: Mapping[str, Any] | None = None) -> Any:
        proc = self._ensure()
        assert proc.stdin and proc.stdout
        payload = {"op": op, "args": dict(args or {})}
        proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            err = ""
            if proc.stderr:
                err = proc.stderr.read()
            raise SiwcError("bridge_closed", f"Bridge encerrou inesperadamente. {err}".strip())
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SiwcError("bridge_protocol", f"Resposta inválida do bridge: {exc}") from exc
        if not message.get("ok"):
            error = message.get("error") or {}
            raise SiwcError(
                str(error.get("code") or "unknown"),
                str(error.get("message") or "Falha no Sign in with ChatGPT."),
                retryable=bool(error.get("retryable")),
            )
        return message.get("result")

    def chat_stream(
        self,
        *,
        model: str,
        message: str,
        instructions: str | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> str:
        proc = self._ensure()
        assert proc.stdin and proc.stdout
        args: dict[str, Any] = {"model": model, "input": message}
        if instructions:
            args["instructions"] = instructions
        proc.stdin.write(json.dumps({"op": "chat", "args": args}, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        collected = ""
        while True:
            line = proc.stdout.readline()
            if not line:
                err = proc.stderr.read() if proc.stderr else ""
                raise SiwcError("bridge_closed", f"Bridge encerrou durante o chat. {err}".strip())
            try:
                message_obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SiwcError("bridge_protocol", f"Resposta inválida do bridge: {exc}") from exc
            if message_obj.get("event") == "delta":
                delta = str(message_obj.get("text") or "")
                collected += delta
                if on_delta:
                    on_delta(delta)
                continue
            if not message_obj.get("ok"):
                error = message_obj.get("error") or {}
                raise SiwcError(
                    str(error.get("code") or "unknown"),
                    str(error.get("message") or "Falha na conversa."),
                    retryable=bool(error.get("retryable")),
                )
            result = message_obj.get("result") or {}
            text = str(result.get("text") or collected)
            return text


def format_session(session: Mapping[str, Any]) -> list[str]:
    status = session.get("status", "disconnected")
    sharing = bool(session.get("sharing"))
    identity = session.get("identity") or {}
    label = session.get("profileLabel") or "—"
    email = identity.get("email") or "—"
    name = identity.get("name") or "—"
    lines = [
        f"Status da sessão: {status}",
        f"Perfil: {label}",
        f"Conta: {name} <{email}>",
        f"Uso do plano ChatGPT (session.sharing): {'sim' if sharing else 'não'}",
    ]
    if status == "connected" and not sharing:
        lines.append(
            "Login de identidade OK, mas o consentimento de uso do plano não está ativo. "
            "Rode: ryoku login --reconsent"
        )
    error = session.get("error")
    if error:
        lines.append(f"Aviso: [{error.get('code')}] {error.get('message')}")
    return lines
