"""Provedores opcionais de visão multimodal (SIWC atual é só texto)."""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import shutil
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .attachments import IMAGE_EXTENSIONS, AttachmentError, max_file_bytes, validate_source_path

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "moondream:1.8b"
DEFAULT_MAX_IMAGE_B64_CHARS = 12_000_000
ALLOWED_BACKENDS = frozenset({"ollama"})
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class VisionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VisionResult:
    text: str
    backend: str
    model: str


@dataclass(frozen=True)
class VisionSettings:
    """Configuração efetiva: env explícito vence o arquivo TOML."""

    backend: str | None
    model: str
    host: str
    allow_remote: bool
    source: str  # env | file | default
    config_path: Path | None
    enabled: bool


def default_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "ryoku-ai" / "vision.toml"


def _parse_bool(raw: Any, *, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return default


def _validate_model(model: str) -> str:
    value = model.strip()
    if not value or not MODEL_RE.match(value):
        raise VisionError("invalid_model", f"Modelo de visão inválido: {model!r}")
    return value


def _validate_host(host: str, *, allow_remote: bool) -> str:
    raw = host.strip().rstrip("/")
    if not raw:
        raise VisionError("invalid_host", "Host Ollama vazio.")
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    if parsed.scheme not in {"http", "https"}:
        raise VisionError("invalid_host", "Host Ollama deve usar http ou https.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise VisionError("invalid_host", "Host Ollama não pode incluir credenciais/query.")
    hostname = parsed.hostname or ""
    if not hostname:
        raise VisionError("invalid_host", "Host Ollama sem hostname.")
    local_names = {"localhost", "127.0.0.1", "::1"}
    is_local = hostname in local_names
    if not is_local:
        try:
            is_local = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_local = False
    if not is_local and not allow_remote:
        raise VisionError(
            "remote_host_denied",
            "Host Ollama remoto bloqueado. Use 127.0.0.1/localhost ou allow_remote=true "
            "(e RYOKU_VISION_ALLOW_REMOTE=1) com ciência do risco.",
        )
    netloc = parsed.netloc
    path = parsed.path.rstrip("/") if parsed.path not in {"", "/"} else ""
    return f"{parsed.scheme}://{netloc}{path}"


def _validate_backend(backend: str | None) -> str | None:
    if backend is None:
        return None
    value = str(backend).strip().lower()
    if value in {"", "off", "none", "disabled"}:
        return None
    if value in {"1", "true", "yes", "on"}:
        return "ollama"
    if value not in ALLOWED_BACKENDS:
        raise VisionError(
            "invalid_backend",
            f"Backend de visão não suportado: {backend!r}. Use ollama ou off.",
        )
    return value


def _load_toml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VisionError("config_unreadable", f"Não foi possível ler {path}: {exc}") from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise VisionError("config_invalid", f"TOML inválido em {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise VisionError("config_invalid", f"{path} deve conter uma tabela TOML.")
    # Apenas chaves conhecidas — nunca executar conteúdo.
    allowed = {"backend", "model", "host", "allow_remote"}
    unknown = set(data) - allowed
    if unknown:
        raise VisionError(
            "config_invalid",
            f"Chaves desconhecidas em {path}: {', '.join(sorted(unknown))}",
        )
    return data


def load_vision_settings(*, config_path: Path | None = None) -> VisionSettings:
    """Resolve settings: variáveis de ambiente explícitas > vision.toml > desligado."""
    path = config_path or default_config_path()
    file_data = _load_toml_file(path)

    def _env(name: str) -> str | None:
        if name not in os.environ:
            return None
        return os.environ.get(name)

    env_backend = _env("RYOKU_VISION_BACKEND")
    env_model = _env("RYOKU_VISION_MODEL")
    env_host = _env("RYOKU_OLLAMA_HOST")
    env_remote = _env("RYOKU_VISION_ALLOW_REMOTE")

    allow_remote = _parse_bool(file_data.get("allow_remote"), default=False)
    if env_remote is not None:
        allow_remote = _parse_bool(env_remote, default=False)

    # String vazia no backend desliga (vence o arquivo). Model/host vazios caem no arquivo/default.
    if env_backend is not None:
        backend_raw: Any = env_backend
    else:
        backend_raw = file_data.get("backend")
    if env_model is not None and str(env_model).strip():
        model_raw: Any = env_model
    else:
        model_raw = file_data.get("model", DEFAULT_OLLAMA_MODEL)
    if env_host is not None and str(env_host).strip():
        host_raw: Any = env_host
    else:
        host_raw = file_data.get("host", DEFAULT_OLLAMA_HOST)

    backend = _validate_backend(None if backend_raw is None else str(backend_raw))

    if env_backend is not None or (env_model is not None and str(env_model).strip()) or (
        env_host is not None and str(env_host).strip()
    ):
        source = "env"
    elif path.is_file() and file_data:
        source = "file"
    else:
        source = "default"

    if backend is None:
        return VisionSettings(
            backend=None,
            model=DEFAULT_OLLAMA_MODEL,
            host=DEFAULT_OLLAMA_HOST,
            allow_remote=False,
            source=source,
            config_path=path if path.is_file() else None,
            enabled=False,
        )

    model = _validate_model(str(model_raw or DEFAULT_OLLAMA_MODEL))
    host = _validate_host(str(host_raw or DEFAULT_OLLAMA_HOST), allow_remote=allow_remote)

    return VisionSettings(
        backend=backend,
        model=model,
        host=host,
        allow_remote=allow_remote,
        source=source,
        config_path=path if path.is_file() else None,
        enabled=True,
    )


# Compatível com chamadas anteriores.
def vision_env_backend() -> str:
    settings = load_vision_settings()
    return settings.backend or ""


def ollama_host() -> str:
    return load_vision_settings().host


def ollama_model() -> str:
    return load_vision_settings().model


def siwc_supports_images() -> bool:
    """Confirmado no vendor: ResponseInputMessage.content é string apenas."""
    return False


def _http_json(url: str, payload: dict[str, Any] | None = None, *, timeout: float = 8.0) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="GET" if data is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:240]
        raise VisionError("ollama_http", f"Ollama HTTP {exc.code}: {body or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise VisionError("ollama_unreachable", f"Ollama indisponível em {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise VisionError("ollama_timeout", f"Timeout ao falar com Ollama ({url}).") from exc
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VisionError("ollama_invalid_json", "Resposta Ollama inválida.") from exc


def probe_ollama(settings: VisionSettings | None = None) -> dict[str, Any]:
    """Somente leitura — nunca faz pull/download de modelos."""
    cfg = settings or load_vision_settings()
    host = cfg.host
    model = cfg.model
    binary = shutil.which("ollama")
    info: dict[str, Any] = {
        "provider": "ollama",
        "host": host,
        "configured_model": model,
        "binary": binary,
        "reachable": False,
        "model_installed": False,
        "installed_models": [],
        "error": None,
    }
    try:
        tags = _http_json(f"{host}/api/tags", timeout=3.0)
    except VisionError as exc:
        info["error"] = {"code": exc.code, "message": exc.message}
        return info
    info["reachable"] = True
    names: list[str] = []
    if isinstance(tags, dict):
        for item in tags.get("models") or []:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
    info["installed_models"] = names
    family = model.split(":")[0]
    info["model_installed"] = any(
        name == model or name.startswith(model + "-") or (":" not in model and name.split(":")[0] == family)
        for name in names
    )
    return info


def hardware_notes(settings: VisionSettings | None = None) -> dict[str, Any]:
    cfg = settings or load_vision_settings()
    mem_available_kb = None
    mem_total_kb = None
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                mem_available_kb = int(line.split()[1])
            elif line.startswith("MemTotal:"):
                mem_total_kb = int(line.split()[1])
    except OSError:
        pass

    nvidia_ok = False
    nvidia_detail = "nvidia-smi ausente"
    if shutil.which("nvidia-smi"):
        try:
            import subprocess

            completed = subprocess.run(
                ["nvidia-smi", "-L"],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            if completed.returncode == 0 and (completed.stdout or "").strip():
                nvidia_ok = True
                nvidia_detail = (completed.stdout or "").strip().splitlines()[0][:120]
            else:
                nvidia_detail = (
                    (completed.stderr or completed.stdout or "driver indisponível").strip()[:160]
                    or "driver NVIDIA indisponível"
                )
        except OSError:
            nvidia_detail = "falha ao executar nvidia-smi"

    return {
        "mem_total_gib": round((mem_total_kb or 0) / (1024 * 1024), 1) if mem_total_kb else None,
        "mem_available_gib": round((mem_available_kb or 0) / (1024 * 1024), 1) if mem_available_kb else None,
        "nvidia_smi_present": shutil.which("nvidia-smi") is not None,
        "nvidia_usable": nvidia_ok,
        "nvidia_detail": nvidia_detail,
        "ollama_installed": shutil.which("ollama") is not None,
        "recommended_model": cfg.model or DEFAULT_OLLAMA_MODEL,
        "recommended_ram_gib": 8 if "moondream" in (cfg.model or "") else 16,
        "recommended_vram_gib": 0 if "moondream" in (cfg.model or "") else 6,
        "note_pt": (
            f"Modelo configurado: `{cfg.model}`. "
            "moondream:1.8b é leve (CPU ok com ~8 GiB RAM). "
            "llava:7b (~4.7 GiB) pede ~8 GiB+ livres ou ~6 GiB VRAM. "
            f"GPU: {nvidia_detail}. "
            "Ryoku não faz pull automático de modelos."
        ),
    }


def vision_capabilities() -> dict[str, Any]:
    try:
        settings = load_vision_settings()
        config_error = None
    except VisionError as exc:
        settings = VisionSettings(
            backend=None,
            model=DEFAULT_OLLAMA_MODEL,
            host=DEFAULT_OLLAMA_HOST,
            allow_remote=False,
            source="default",
            config_path=default_config_path() if default_config_path().is_file() else None,
            enabled=False,
        )
        config_error = {"code": exc.code, "message": exc.message}

    opt_in = settings.enabled
    hw = hardware_notes(settings)
    should_probe = opt_in or hw["ollama_installed"] or settings.source == "file"
    ollama = (
        probe_ollama(settings)
        if should_probe
        else {
            "provider": "ollama",
            "reachable": False,
            "model_installed": False,
            "configured_model": settings.model,
            "host": settings.host,
            "skipped": True,
            "reason": "sem opt-in (arquivo/env) e probe adiado",
        }
    )

    provider_name = settings.backend if opt_in else None
    available = bool(
        provider_name == "ollama"
        and isinstance(ollama, dict)
        and ollama.get("reachable")
        and ollama.get("model_installed")
    )

    if config_error:
        message = f"Configuração de visão inválida: {config_error['message']}"
    elif not opt_in:
        message = (
            "Análise de imagens indisponível: @siwc/local aceita somente texto. "
            "Crie ~/.config/ryoku-ai/vision.toml (backend=\"ollama\") "
            "ou exporte RYOKU_VISION_BACKEND=ollama. "
            "Requer Ollama + modelo já instalado; Ryoku não faz pull. "
            "Obs.: o Quickshell frequentemente não herda env do user systemd — prefira o TOML."
        )
    elif not ollama.get("reachable"):
        message = (
            "Visão opt-in ativa, mas Ollama não responde em "
            f"{settings.host}. Inicie o serviço — sem download automático pelo Ryoku."
        )
    elif not ollama.get("model_installed"):
        message = (
            f"Ollama alcançável, mas o modelo `{settings.model}` não está instalado. "
            f"Instale manualmente após autorização (ex.: `ollama pull {settings.model}`). "
            "Ryoku não baixa modelos sozinho."
        )
    else:
        message = f"Visão disponível via Ollama (`{settings.model}`), fonte={settings.source}."

    return {
        "vision_available": available,
        "siwc_text_only": True,
        "siwc_supports_images": siwc_supports_images(),
        "opt_in_env": "RYOKU_VISION_BACKEND",
        "opt_in_set": opt_in,
        "config": {
            "path": str(settings.config_path) if settings.config_path else str(default_config_path()),
            "exists": bool(settings.config_path and settings.config_path.is_file()),
            "source": settings.source,
            "backend": settings.backend,
            "model": settings.model,
            "host": settings.host,
            "allow_remote": settings.allow_remote,
            "error": config_error,
        },
        "provider": provider_name,
        "ollama": ollama,
        "hardware": hw,
        "message": message,
        "no_auto_download": True,
        "no_siwc_token_reuse": True,
    }


def encode_image_b64(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > max_file_bytes():
        raise AttachmentError("too_large", f"{path.name} excede o limite de anexos.")
    encoded = base64.b64encode(data).decode("ascii")
    if len(encoded) > int(os.environ.get("RYOKU_VISION_MAX_B64", DEFAULT_MAX_IMAGE_B64_CHARS)):
        raise VisionError("image_too_heavy", f"{path.name}: payload base64 grande demais para o backend.")
    return encoded


def analyze_with_ollama(image_paths: list[Path], prompt: str) -> VisionResult:
    caps = vision_capabilities()
    if not caps.get("opt_in_set"):
        raise VisionError("vision_not_enabled", caps["message"])
    if not caps.get("vision_available"):
        raise VisionError("vision_unavailable", caps["message"])
    settings = load_vision_settings()
    model = settings.model
    images = [encode_image_b64(path) for path in image_paths]
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": images,
            }
        ],
    }
    result = _http_json(f"{settings.host}/api/chat", payload, timeout=180.0)
    if not isinstance(result, dict):
        raise VisionError("ollama_invalid_json", "Resposta Ollama vazia.")
    message = result.get("message") if isinstance(result.get("message"), dict) else {}
    text = str(message.get("content") or "").strip()
    if not text:
        raise VisionError("empty_vision_response", "O modelo de visão não retornou texto.")
    used_model = str(result.get("model") or model)
    return VisionResult(text=text, backend="ollama", model=used_model)


def analyze_images(image_paths: list[Path], prompt: str) -> VisionResult:
    if not image_paths:
        raise VisionError("no_images", "Nenhuma imagem para analisar.")
    for path in image_paths:
        validate_source_path(path)
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise AttachmentError("unsupported_type", f"Não é imagem suportada: {path.name}")
    settings = load_vision_settings()
    if settings.backend == "ollama":
        return analyze_with_ollama(image_paths, prompt)
    raise VisionError(
        "vision_unavailable",
        vision_capabilities()["message"],
    )


def write_example_config(path: Path | None = None, *, force: bool = False) -> Path:
    """Escreve um vision.toml de exemplo (não sobrescreve sem force)."""
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        return target
    contents = (
        "# Configuração persistente de visão do Ryoku (lida pela CLI mesmo sem env no Quickshell).\n"
        "# Env explícito (RYOKU_VISION_BACKEND / RYOKU_VISION_MODEL / RYOKU_OLLAMA_HOST) tem precedência.\n"
        'backend = "ollama"\n'
        'model = "moondream:1.8b"\n'
        'host = "http://127.0.0.1:11434"\n'
        "# allow_remote = false\n"
    )
    target.write_text(contents, encoding="utf-8")
    os.chmod(target, 0o600)
    return target
