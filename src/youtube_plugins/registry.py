from __future__ import annotations

import importlib.util
import os
import shutil
from dataclasses import asdict, dataclass
from typing import Any, Dict, List


@dataclass
class PluginStatus:
    name: str
    available: bool
    status: str = "unavailable"
    command: str = ""
    path: str = ""
    role: str = ""
    required: bool = False
    warning: str = ""
    check_type: str = "command"
    module: str = ""
    env_var: str = ""
    notes: str = ""


PLUGIN_SPECS = {
    "summarize": {"command": "summarize", "role": "cli_extraction_engine", "check_type": "command"},
    "transcribe_critic": {"module": "youtube_external_bridge.transcribe_critic_bridge", "role": "trusted_transcript_bridge", "check_type": "internal_module"},
    "faster_whisper": {"module": "faster_whisper", "role": "local_asr_fallback", "check_type": "python_module"},
    "whisperx": {"module": "whisperx", "role": "optional_alignment_asr", "check_type": "python_module"},
    "paddleocr": {"module": "paddleocr", "role": "ocr_fallback", "check_type": "python_module"},
    "tesseract": {"command": "tesseract", "role": "ocr_fallback", "check_type": "command"},
    "gemini_flash": {"env_var": "GEMINI_API_KEY", "role": "first_pass_model", "check_type": "env"},
    "codex_review": {"module": "youtube_model_flow.codex_review_pack", "role": "final_review_pack_builder", "check_type": "internal_module"},
    "python": {"command": "python", "role": "runtime", "check_type": "command"},
}

# Acquisition/media tooling is intentionally NOT part of the public alpha plugin
# discovery surface. The public package ships synthetic fixtures and accepts
# operator-provided knowledge records only; it does not bundle a YouTube media
# download or media-processing path. Lawful transcript/caption acquisition is the
# operator's responsibility and lives outside this package.
EXCLUDED_FROM_PUBLIC_DISCOVERY = ("yt_dlp", "ffmpeg")


def check_plugin(name: str, required: bool = False) -> PluginStatus:
    spec: Dict[str, Any] = PLUGIN_SPECS.get(name, {"command": name, "role": "external", "check_type": "command"})
    cmd = spec.get("command", "")
    module = spec.get("module", "")
    env_var = spec.get("env_var", "")
    check_type = spec.get("check_type", "command")
    path = shutil.which(cmd) or "" if cmd else ""
    try:
        module_available = bool(module and importlib.util.find_spec(module))
    except ModuleNotFoundError:
        module_available = False
    env_available = bool(env_var and os.environ.get(env_var))
    available = bool(path) or module_available or env_available
    status = "available" if available else "unavailable"
    notes = ""
    if check_type == "env" and not env_available:
        status = "not_configured"
        notes = f"{env_var} is not set; optional model lane skipped"
    elif check_type in {"python_module", "internal_module"} and not module_available:
        status = "unavailable"
        notes = f"Python module {module} not importable"
    elif check_type == "command_or_module":
        available = bool(path) or module_available
        status = "available" if available else "unavailable"
        if not available:
            notes = f"{cmd} command and {module} module not found"
    elif check_type == "command" and not path:
        notes = f"{cmd} not found"
    return PluginStatus(
        name=name,
        available=available,
        status=status,
        command=cmd,
        path=path,
        role=spec.get("role", ""),
        required=required,
        warning="" if available else notes + ("; required" if required else "; optional"),
        check_type=check_type,
        module=module,
        env_var=env_var,
        notes=notes,
    )


def check_all() -> List[Dict]:
    return [asdict(check_plugin(name)) for name in PLUGIN_SPECS]
