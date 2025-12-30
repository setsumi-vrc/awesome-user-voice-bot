"""Talkback bot - Real-time voice interaction client for VRChat."""
from app.audio import CrossPlatformRecorder, pcm16le_to_rms, create_silence_frame, play_wav_file
from app.config import Config, load_config
from app.metrics import Metrics, metrics_logger
from app.tts_client import TTSClient
from app.vad import VADState
from app.websocket import WebSocketHandler

__version__ = "2.0.0"
__all__ = [
    "Config",
    "load_config",
    "Metrics",
    "metrics_logger",
    "CrossPlatformRecorder",
    "TTSClient",
    "VADState",
    "WebSocketHandler",
    "pcm16le_to_rms",
    "create_silence_frame",
    "play_wav_file",
]
