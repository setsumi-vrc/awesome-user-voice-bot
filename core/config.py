from pathlib import Path
from dataclasses import dataclass
import os
from functools import lru_cache

try:
    import yaml
except Exception:
    yaml = None


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    # Logging
    LOG_LEVEL: str = "WARNING"
    FILTER_HEALTH_LOGS: bool = True
    MAX_CONVERSATION_LOG_ENTRIES: int = 100
    
    # Audio / STT
    SAMPLE_RATE: int = 16000
    SILENCE_RMS_THRESHOLD: float = 0.008
    SILENCE_MAX_SECONDS: float = 0.7
    MIN_UTTERANCE_SECONDS: float = 0.35
    MAX_UTTERANCE_SECONDS: float = 12.0
    MAX_BUFFER_SECONDS: float = 120.0

    # Model (Whisper / faster-whisper)
    WHISPER_MODEL_NAME: str = "small"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_LANG: str = "en"
    WHISPER_BEAM: int = 1

    # CUDA paths (Windows) - pass absolute paths via config
    CUDA_X64_PATH: str = ""
    CUDNN_BIN_PATH: str = ""

    # Ollama LLM
    OLLAMA_URL: str = "http://127.0.0.1:11434/api/generate"
    OLLAMA_MODEL: str = "dagbs/darkidol-llama-3.1-8b-instruct-1.0-uncensored"
    OLLAMA_TIMEOUT: int = 30
    OLLAMA_RETRY_ATTEMPTS: int = 3
    OLLAMA_RETRY_BACKOFF: float = 1.0

    # Circuit Breaker
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAIL_MAX: int = 5
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = 60
    CIRCUIT_BREAKER_EXPECTED_EXCEPTION: str = "requests.exceptions.RequestException"

    # Piper TTS
    PIPER_BIN: str = "piper"
    PIPER_MODEL_PATH: str = ""
    PIPER_CONFIG_PATH: str = ""
    PIPER_SPEAKER_ID: int = 12

    # TTS Validation
    TTS_MAX_TEXT_LENGTH: int = 500
    TTS_REQUEST_TIMEOUT: int = 60
    TTS_MAX_CONCURRENT: int = 4

    # Paths
    SYSTEM_PROMPT_PATH: str = ""
    VOICES_DIR: str = ""

    # Piper voice tuning
    PIPER_LENGTH_SCALE: float = 1.05
    PIPER_NOISE_SCALE: float = 0.6
    PIPER_NOISE_W: float = 0.7

    # Server Configuration
    STT_HOST: str = "0.0.0.0"
    STT_PORT: int = 8010
    TTS_HOST: str = "0.0.0.0"
    TTS_PORT: int = 8000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from config.yaml if available, otherwise use defaults/env vars.
    
    Cached to avoid repeated file reads. Clear cache with get_settings.cache_clear().
    """
    cfg_path = os.environ.get("CONFIG_PATH", str(BASE_DIR / "config.yaml"))

    data = {}
    if Path(cfg_path).exists():
        if yaml is None:
            raise RuntimeError(
                "config.yaml found but PyYAML is not installed. Install with: pip install pyyaml"
            )
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    def _val(key: str, default):
        """Get value from YAML, env var, or default."""
        if key in data:
            return data[key]
        return os.environ.get(key.upper(), default)

    def _resolve_path(path_str: str) -> str:
        """Resolve path relative to BASE_DIR / 'voices' if relative, otherwise return as-is."""
        if not path_str:
            return ""
        p = Path(path_str)
        if p.is_absolute():
            return str(p)
        return str(BASE_DIR / "voices" / path_str)

    piper_model = str(_val("piper_model_path", "en_US-kusal-medium.onnx"))
    piper_config = str(_val("piper_config_path", "en_US-kusal-medium.onnx.json"))

    return Settings(
        LOG_LEVEL=str(_val("log_level", "WARNING")).upper(),
        FILTER_HEALTH_LOGS=bool(_val("filter_health_logs", True)),
        MAX_CONVERSATION_LOG_ENTRIES=int(_val("max_conversation_log_entries", 100)),
        SAMPLE_RATE=int(_val("sample_rate", 16000)),
        SILENCE_RMS_THRESHOLD=float(_val("silence_rms_threshold", 0.008)),
        SILENCE_MAX_SECONDS=float(_val("silence_max_seconds", 0.7)),
        MIN_UTTERANCE_SECONDS=float(_val("min_utterance_seconds", 0.35)),
        MAX_UTTERANCE_SECONDS=float(_val("max_utterance_seconds", 12.0)),
        MAX_BUFFER_SECONDS=float(_val("max_buffer_seconds", 120.0)),
        WHISPER_MODEL_NAME=str(_val("whisper_model_name", "small")),
        WHISPER_DEVICE=str(_val("whisper_device", "cuda")),
        WHISPER_COMPUTE_TYPE=str(_val("whisper_compute_type", "float16")),
        WHISPER_LANG=str(_val("whisper_lang", "en")),
        WHISPER_BEAM=int(_val("whisper_beam", 1)),
        CUDA_X64_PATH=str(_val("cuda_x64_path", "")),
        CUDNN_BIN_PATH=str(_val("cudnn_bin_path", "")),
        OLLAMA_URL=str(_val("ollama_url", "http://127.0.0.1:11434/api/generate")),
        OLLAMA_MODEL=str(_val("ollama_model", "dagbs/darkidol-llama-3.1-8b-instruct-1.0-uncensored")),
        OLLAMA_TIMEOUT=int(_val("ollama_timeout", 30)),
        OLLAMA_RETRY_ATTEMPTS=int(_val("ollama_retry_attempts", 3)),
        OLLAMA_RETRY_BACKOFF=float(_val("ollama_retry_backoff", 1.0)),
        CIRCUIT_BREAKER_ENABLED=bool(_val("circuit_breaker_enabled", True)),
        CIRCUIT_BREAKER_FAIL_MAX=int(_val("circuit_breaker_fail_max", 5)),
        CIRCUIT_BREAKER_RESET_TIMEOUT=int(_val("circuit_breaker_reset_timeout", 60)),
        CIRCUIT_BREAKER_EXPECTED_EXCEPTION=str(_val("circuit_breaker_expected_exception", "requests.exceptions.RequestException")),
        PIPER_BIN=str(_val("piper_bin", "piper")),
        PIPER_MODEL_PATH=_resolve_path(piper_model),
        PIPER_CONFIG_PATH=_resolve_path(piper_config),
        PIPER_SPEAKER_ID=int(_val("piper_speaker_id", 12)),
        TTS_MAX_TEXT_LENGTH=int(_val("tts_max_text_length", 500)),
        TTS_REQUEST_TIMEOUT=int(_val("tts_request_timeout", 60)),
        TTS_MAX_CONCURRENT=int(_val("tts_max_concurrent", 4)),
        SYSTEM_PROMPT_PATH=str(_val("system_prompt_path", str(BASE_DIR / "system_prompt.txt"))),
        VOICES_DIR=str(_val("voices_dir", str(BASE_DIR / "voices"))),
        PIPER_LENGTH_SCALE=float(_val("piper_length_scale", 1.0)),
        PIPER_NOISE_SCALE=float(_val("piper_noise_scale", 0.667)),
        PIPER_NOISE_W=float(_val("piper_noise_w", 0.8)),
        STT_HOST=str(_val("stt_host", "0.0.0.0")),
        STT_PORT=int(_val("stt_port", 8010)),
        TTS_HOST=str(_val("tts_host", "0.0.0.0")),
        TTS_PORT=int(_val("tts_port", 8000)),
    )
