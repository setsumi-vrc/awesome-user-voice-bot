import subprocess
import tempfile
import logging
import shutil
import sys
from pathlib import Path

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PiperError(Exception):
    """Exception raised when Piper TTS operations fail."""
    pass


def _find_piper_executable() -> str:
    """Find Piper executable, checking common locations and PATH.
    
    Returns:
        Path to Piper executable.
        
    Raises:
        PiperError: If Piper executable cannot be found.
    """
    # On Windows, ensure we're looking for .exe
    piper_name = settings.PIPER_BIN
    if sys.platform == "win32" and not piper_name.endswith(".exe"):
        piper_name_with_exe = piper_name + ".exe"
        # Check if .exe version exists in PATH first
        if shutil.which(piper_name_with_exe):
            return piper_name_with_exe
    
    # Check if executable exists in PATH
    piper_path = shutil.which(piper_name)
    if piper_path:
        return piper_path
    
    # Check common Windows installation locations
    if sys.platform == "win32":
        common_paths = [
            Path("C:/Program Files/piper/piper.exe"),
            Path("C:/Program Files (x86)/piper/piper.exe"),
            Path.home() / "AppData/Local/Programs/piper/piper.exe",
            Path("piper.exe"),  # Current directory
        ]
        for path in common_paths:
            if path.exists():
                return str(path)
    
    # Piper not found - provide helpful error message
    install_msg = (
        "Piper TTS executable not found. Please install Piper:\n"
        "\n"
        "Windows:\n"
        "  1. Download from: https://github.com/rhasspy/piper/releases\n"
        "  2. Extract piper.exe to a directory\n"
        "  3. Add to PATH or set piper_bin in config.yaml to full path\n"
        "\n"
        "Linux/macOS:\n"
        "  pip install piper-tts\n"
        "\n"
        f"Current setting: {settings.PIPER_BIN}"
    )
    raise PiperError(install_msg)


def synthesize_text_to_wav(
    text: str,
    model_path: str | None = None,
    config_path: str | None = None,
    speaker_id: int | None = None,
    length_scale: float | None = None,
    noise_scale: float | None = None,
    noise_w: float | None = None
) -> bytes:
    """Synthesize text using Piper and return WAV bytes (in-memory, no disk I/O).
    
    Args:
        text: Text to synthesize into speech.
        model_path: Override default model path.
        config_path: Override default config path.
        speaker_id: Override default speaker ID.
        length_scale: Override default speed (1.0 = normal).
        noise_scale: Override default voice variance.
        noise_w: Override default voice stability.
        
    Returns:
        WAV audio data as bytes.
        
    Raises:
        PiperError: If synthesis fails or required files are missing.
    """
    if not text:
        raise PiperError("empty text")

    # Find Piper executable
    try:
        piper_bin = _find_piper_executable()
    except PiperError:
        raise  # Re-raise with installation instructions

    # Use provided paths or defaults
    model = Path(model_path) if model_path else Path(settings.PIPER_MODEL_PATH)
    config = Path(config_path) if config_path else Path(settings.PIPER_CONFIG_PATH)
    
    if not model.exists():
        raise PiperError(f"Model file not found: {model}")
    if not config.exists():
        raise PiperError(f"Config file not found: {config}")

    # Create a temporary file that persists until we manually delete it
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_wav = f.name

    # Use provided parameters or defaults
    spk_id = speaker_id if speaker_id is not None else settings.PIPER_SPEAKER_ID
    len_scale = length_scale if length_scale is not None else settings.PIPER_LENGTH_SCALE
    noi_scale = noise_scale if noise_scale is not None else settings.PIPER_NOISE_SCALE
    noi_w_val = noise_w if noise_w is not None else settings.PIPER_NOISE_W

    cmd = [
        piper_bin,  # Use validated executable path
        "-m", str(model),
        "-c", str(config),
        "--speaker", str(spk_id),
        "--length-scale", str(len_scale),
        "--noise-scale", str(noi_scale),
        "--noise-w", str(noi_w_val),
        "-f", out_wav,
    ]

    logger.debug(f"Running Piper: {' '.join(cmd)}")
    
    try:
        p = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,  # Prevent hanging
        )
    except FileNotFoundError:
        Path(out_wav).unlink(missing_ok=True)
        raise PiperError(
            f"Piper executable not found: {piper_bin}\n"
            "Please install Piper TTS. See documentation for instructions."
        )
    except subprocess.TimeoutExpired:
        Path(out_wav).unlink(missing_ok=True)
        raise PiperError("Piper process timed out after 30 seconds")

    if p.returncode != 0:
        Path(out_wav).unlink(missing_ok=True)
        stderr_msg = p.stderr.decode("utf-8", "ignore").strip()
        logger.error(f"Piper failed with code {p.returncode}: {stderr_msg}")
        raise PiperError(stderr_msg or f"Piper exited with code {p.returncode}")

    # Read WAV into memory and return bytes
    try:
        with open(out_wav, "rb") as f:
            wav_bytes = f.read()
        logger.debug(f"Generated {len(wav_bytes)} bytes of audio")
        return wav_bytes
    finally:
        # Clean up temp file
        Path(out_wav).unlink(missing_ok=True)
