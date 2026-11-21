"""Provedores opcionais de visão multimodal (SIWC atual é só texto)."""

from __future__ import annotations

import base64
import json
import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .attachments import IMAGE_EXTENSIONS, AttachmentError, max_file_bytes, validate_source_path

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llava:7b"
# Limite de payload base64 por imagem (após validar bytes brutos).
DEFAULT_MAX_IMAGE_B64_CHARS = 12_000_000


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


def vision_env_backend() -> str:
    return os.environ.get("RYOKU_VISION_BACKEND", "").strip().lower()


def ollama_host() -> str:
    return os.environ.get("RYOKU_OLLAMA_HOST", DEFAULT_OLLAMA_HOST).rstrip("/")


def ollama_model() -> str:
    return os.environ.get("RYOKU_VISION_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL


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


def probe_ollama() -> dict[str, Any]:
    """Somente leitura — nunca faz pull/download de modelos."""
    host = ollama_host()
    model = ollama_model()
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
    # Exact match or same tag family (llava:7b == llava:7b, llava matches llava:7b).
    family = model.split(":")[0]
    info["model_installed"] = any(
        name == model or name.startswith(model + "-") or (":" not in model and name.split(":")[0] == family)
        for name in names
    )
    return info


def hardware_notes() -> dict[str, Any]:
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
    nvidia = shutil.which("nvidia-smi") is not None
    return {
        "mem_total_gib": round((mem_total_kb or 0) / (1024 * 1024), 1) if mem_total_kb else None,
        "mem_available_gib": round((mem_available_kb or 0) / (1024 * 1024), 1) if mem_available_kb else None,
        "nvidia_smi": nvidia,
        "ollama_installed": shutil.which("ollama") is not None,
        "recommended_model": DEFAULT_OLLAMA_MODEL,
        "recommended_ram_gib": 16,
        "recommended_vram_gib": 6,
        "note_pt": (
            "llava:7b (~4.7 GiB) costuma precisar de ~8 GiB+ livres (CPU) ou ~6 GiB VRAM. "
            "Neste notebook o driver NVIDIA falhou e Ollama não está instalado — "
            "não baixar modelos sem autorização explícita."
        ),
    }


def vision_capabilities() -> dict[str, Any]:
    env = vision_env_backend()
    opt_in = env in {"1", "true", "yes", "ollama"}
    hw = hardware_notes()
    ollama = probe_ollama() if opt_in or env == "ollama" or hw["ollama_installed"] else {
        "provider": "ollama",
        "reachable": False,
        "model_installed": False,
        "configured_model": ollama_model(),
        "skipped": True,
        "reason": "probe completo só com RYOKU_VISION_BACKEND=ollama ou ollama no PATH",
    }
    if opt_in and env in {"1", "true", "yes"}:
        # Alias genérico → ollama nesta build.
        provider_name = "ollama"
    elif opt_in:
        provider_name = env
    else:
        provider_name = None

    available = bool(
        provider_name == "ollama"
        and isinstance(ollama, dict)
        and ollama.get("reachable")
        and ollama.get("model_installed")
    )
    if not opt_in:
        message = (
            "Análise de imagens indisponível: @siwc/local aceita somente texto. "
            "Ative um backend local opt-in com RYOKU_VISION_BACKEND=ollama "
            "(requer Ollama + modelo multimodal já instalado; Ryoku não faz pull)."
        )
    elif not ollama.get("reachable"):
        message = (
            "Visão opt-in ativa, mas Ollama não responde em "
            f"{ollama_host()}. Instale/inicie o serviço — sem download automático pelo Ryoku."
        )
    elif not ollama.get("model_installed"):
        message = (
            f"Ollama alcançável, mas o modelo `{ollama_model()}` não está instalado. "
            f"Instale manualmente após autorização (ex.: `ollama pull {ollama_model()}`). "
            "Ryoku não baixa modelos sozinho."
        )
    else:
        message = f"Visão disponível via Ollama (`{ollama_model()}`)."

    return {
        "vision_available": available,
        "siwc_text_only": True,
        "siwc_supports_images": siwc_supports_images(),
        "opt_in_env": "RYOKU_VISION_BACKEND",
        "opt_in_set": opt_in,
        "provider": provider_name if opt_in else None,
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
    model = ollama_model()
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
    # Análise pode demorar; timeout alto, sem logar bytes.
    result = _http_json(f"{ollama_host()}/api/chat", payload, timeout=180.0)
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
    backend = vision_env_backend()
    if backend in {"1", "true", "yes", "ollama"}:
        return analyze_with_ollama(image_paths, prompt)
    raise VisionError(
        "vision_unavailable",
        vision_capabilities()["message"],
    )
