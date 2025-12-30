"""Configuration loader for talkback client."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ServerConfig:
    """Server endpoint configuration."""
    pc_ip: str
    stt_port: int
    tts_port: int
    
    @property
    def stt_ws_url(self) -> str:
        return f"ws://{self.pc_ip}:{self.stt_port}/ws/stt"
    
    @property
    def tts_url(self) -> str:
        return f"http://{self.pc_ip}:{self.tts_port}/tts"


@dataclass
class AudioConfig:
    """Audio processing configuration."""
    sample_rate: int
    chunk_ms: int
    input_device: Optional[str]
    output_device: Optional[str]
    
    @property
    def chunk_frames(self) -> int:
        return int(self.sample_rate * self.chunk_ms / 1000)
    
    @property
    def bytes_per_chunk(self) -> int:
        return self.chunk_frames * 2  # PCM16 mono


@dataclass
class VADConfig:
    """Voice Activity Detection configuration."""
    silence_rms_threshold: float
    silence_max_seconds: float
    min_utterance_seconds: float
    utterance_cooldown: float
    silence_tail_frames: int


@dataclass
class QueueConfig:
    """Queue settings."""
    max_size: int
    get_timeout: float


@dataclass
class ResponseConfig:
    """Response behavior configuration."""
    cooldown_seconds: float


@dataclass
class WebSocketConfig:
    """WebSocket connection configuration."""
    ping_interval: float
    ping_timeout: float
    reconnect_delay: float
    max_size: int
    max_queue: int
    write_limit: int


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str
    format: str
    date_format: str


@dataclass
class MetricsConfig:
    """Metrics configuration."""
    enabled: bool
    log_interval: float


@dataclass
class Config:
    """Complete application configuration."""
    server: ServerConfig
    audio: AudioConfig
    vad: VADConfig
    queue: QueueConfig
    response: ResponseConfig
    websocket: WebSocketConfig
    logging: LoggingConfig
    metrics: MetricsConfig


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from YAML file.
    
    Args:
        config_path: Path to config.yaml. Defaults to client/config.yaml.
        
    Returns:
        Complete configuration object.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return Config(
        server=ServerConfig(**data['server']),
        audio=AudioConfig(**data['audio']),
        vad=VADConfig(**data['vad']),
        queue=QueueConfig(**data['queue']),
        response=ResponseConfig(**data['response']),
        websocket=WebSocketConfig(**data['websocket']),
        logging=LoggingConfig(**data['logging']),
        metrics=MetricsConfig(**data['metrics'])
    )
