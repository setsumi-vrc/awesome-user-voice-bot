"""Cross-platform audio processing using sounddevice."""
import asyncio
import io
import logging
import os
import platform
import subprocess
import sys
import tempfile
import wave
from contextlib import suppress
from typing import List, Optional, Tuple

import numpy as np
import sounddevice as sd

from app.config import AudioConfig

logger = logging.getLogger(__name__)


def pcm16le_to_rms(pcm_bytes: bytes) -> float:
    """Calculate RMS (Root Mean Square) of PCM16LE audio.
    
    Args:
        pcm_bytes: Raw PCM16LE audio bytes.
        
    Returns:
        RMS value (0.0 to 1.0).
    """
    if not pcm_bytes:
        return 0.0
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(audio * audio) + 1e-12))


def create_silence_frame(bytes_per_chunk: int) -> bytes:
    """Create a silent audio frame.
    
    Args:
        bytes_per_chunk: Size of the frame in bytes.
        
    Returns:
        Silent PCM16LE frame.
    """
    return b"\x00" * bytes_per_chunk


async def play_wav_file(wav_bytes: bytes, output_device: Optional[str] = None) -> None:
    """Play WAV audio through sounddevice.
    
    Args:
        wav_bytes: WAV file content as bytes.
        output_device: Device name substring or None for default.
    """
    def _resolve_output_device_index(name: Optional[str]) -> Optional[int]:
        if name is None:
            return None
        requested = name.strip().lower()
        best_idx: Optional[int] = None
        best_score = -1
        for idx, dev in enumerate(sd.query_devices()):
            try:
                out_ch = int(dev.get("max_output_channels", 0) or 0)
                dev_name = str(dev.get("name", ""))
            except Exception:
                continue
            if out_ch <= 0:
                continue
            nl = dev_name.lower()
            if nl == requested:
                return idx
            if requested in nl:
                score = 1000 + len(requested)
                if score > best_score:
                    best_score = score
                    best_idx = idx
        return best_idx

    def _decode_wav_to_float32(wav_data: bytes) -> tuple[np.ndarray, int]:
        with wave.open(io.BytesIO(wav_data), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sample_rate = wf.getframerate()
            frames = wf.getnframes()
            raw = wf.readframes(frames)

        if sampwidth != 2:
            raise ValueError(f"Unsupported WAV sample width: {sampwidth * 8} bits")

        audio_i16 = np.frombuffer(raw, dtype=np.int16)
        if channels > 1:
            audio_i16 = audio_i16.reshape(-1, channels)
            audio_i16 = audio_i16.mean(axis=1).astype(np.int16)

        audio_f32 = audio_i16.astype(np.float32) / 32768.0
        return audio_f32, sample_rate

    device_index = _resolve_output_device_index(output_device)
    if output_device is not None and device_index is None:
        logger.warning(f"Output device '{output_device}' not found; using default output")

    audio_f32, sample_rate = _decode_wav_to_float32(wav_bytes)

    def _play_blocking() -> None:
        sd.play(audio_f32, samplerate=sample_rate, device=device_index)
        sd.wait()

    await asyncio.to_thread(_play_blocking)


class CrossPlatformRecorder:
    """Cross-platform audio recorder using sounddevice."""
    
    def __init__(self, audio_config: AudioConfig):
        """Initialize recorder.
        
        Args:
            audio_config: Audio configuration.
        """
        self.config = audio_config
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._stream: Optional[sd.InputStream] = None
        self._device_index: Optional[int] = None
        self._running = False
        self._callback_errors: asyncio.Queue = asyncio.Queue()
    
    def _find_device(self, device_name: Optional[str]) -> Optional[int]:
        """Resolve an INPUT (capture) device index by substring.

        This searches only devices with `max_input_channels > 0`.

        Args:
            device_name: Name substring to match (case-insensitive). If None, use default input.

        Returns:
            Device index, or None to use the default input device.
        """
        if device_name is None:
            logger.info("Input device: [default]")
            return None

        requested = device_name.strip()
        requested_l = requested.lower()

        devices = sd.query_devices()
        logger.info(f"Searching for INPUT device (requested: '{requested}')")

        candidates: List[Tuple[int, str, int, int]] = []
        for idx, device in enumerate(devices):
            in_ch = int(device.get("max_input_channels", 0) or 0)
            out_ch = int(device.get("max_output_channels", 0) or 0)
            if in_ch > 0:
                candidates.append((idx, str(device.get("name", "")), in_ch, out_ch))

        def match_score(name: str) -> int:
            nl = name.lower()
            if nl == requested_l:
                return 100000
            if requested_l in nl:
                return 50000 + len(requested_l)  # prefer more specific (longer) substrings
            return -1

        best: Optional[Tuple[int, str, int, int]] = None
        best_score = -1
        ties: List[Tuple[int, str, int, int]] = []

        for candidate in candidates:
            score = match_score(candidate[1])
            if score > best_score:
                best_score = score
                best = candidate
                ties = [candidate]
            elif score == best_score and score >= 0:
                ties.append(candidate)

        if best is not None and best_score >= 0:
            if len(ties) > 1:
                ties_sorted = sorted(ties, key=lambda x: x[0])
                best = ties_sorted[0]
                tie_names = ", ".join([f"[{i}] {n}" for i, n, _, _ in ties_sorted[:5]])
                logger.warning(
                    f"Multiple INPUT devices matched '{requested}'. Using [{best[0]}] '{best[1]}'. Candidates: {tie_names}"
                )

            idx, name, in_ch, out_ch = best
            logger.info(f"✓ Selected INPUT device: [{idx}] {name} ({in_ch} in, {out_ch} out)")
            return idx

        # Helpful hint: user may have provided an OUTPUT device name (common with VoiceMeeter)
        output_matches: List[Tuple[int, str, int]] = []
        for idx, device in enumerate(devices):
            try:
                out_ch = int(device.get("max_output_channels", 0) or 0)
                dev_name = str(device.get("name", ""))
            except Exception:
                continue
            if out_ch <= 0:
                continue
            if requested_l in dev_name.lower():
                output_matches.append((idx, dev_name, out_ch))

        if output_matches:
            example = output_matches[0][1]
            logger.error(
                "The requested device name looks like an OUTPUT (playback) device, but you're configuring INPUT capture. "
                "This usually means input_device/output_device are swapped. "
                f"Example OUTPUT match: [{output_matches[0][0]}] {example}"
            )

        logger.warning(f"INPUT device '{requested}' not found. Available INPUT devices:")
        for idx, name, in_ch, out_ch in candidates:
            logger.warning(f"  [{idx}] {name} ({in_ch} in, {out_ch} out)")

        logger.warning("Using default input device")
        return None
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Audio callback from sounddevice (runs in C thread).
        
        Args:
            indata: Input audio data as numpy array.
            frames: Number of frames.
            time_info: Time information.
            status: Stream status flags.
        """
        if status:
            # Queue errors for async handling
            try:
                self._callback_errors.put_nowait(str(status))
            except asyncio.QueueFull:
                pass
        
        try:
            # Convert numpy array to bytes and queue it
            self._queue.put_nowait(indata.copy().tobytes())
        except asyncio.QueueFull:
            # Drop oldest frame on overrun
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(indata.copy().tobytes())
            except:
                pass
    
    async def start(self) -> None:
        """Start audio capture."""
        if self._running:
            return
        
        # Find device
        self._device_index = self._find_device(self.config.input_device)
        
        # Log selected device
        if self._device_index is not None:
            device_info = sd.query_devices(self._device_index)
            logger.info(
                f"🎧 Starting audio capture: {device_info['name']} "
                f"@ {self.config.sample_rate}Hz, {self.config.chunk_ms}ms chunks"
            )
        else:
            logger.info(
                f"🎧 Starting audio capture: [default device] "
                f"@ {self.config.sample_rate}Hz, {self.config.chunk_ms}ms chunks"
            )
        
        # Create and start stream
        self._stream = sd.InputStream(
            device=self._device_index,
            samplerate=self.config.sample_rate,
            channels=1,
            dtype='int16',
            blocksize=self.config.chunk_frames,
            callback=self._audio_callback,
            latency='low'
        )
        
        self._stream.start()
        self._running = True
    
    async def stop(self) -> None:
        """Stop audio capture."""
        if not self._running or self._stream is None:
            return
        
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._running = False
        logger.info("🎧 Audio capture stopped")
    
    async def read_chunk(self) -> bytes:
        """Read one audio chunk.
        
        Returns:
            PCM16LE audio bytes.
            
        Raises:
            RuntimeError: If callback error occurred or timeout.
        """
        # Check for callback errors
        if not self._callback_errors.empty():
            error = self._callback_errors.get_nowait()
            logger.warning(f"Audio callback status: {error}")
        
        # Read from queue with timeout
        try:
            return await asyncio.wait_for(
                self._queue.get(),
                timeout=self.config.chunk_ms * 5 / 1000  # 5x chunk time
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Audio stream timeout - device may have disconnected")
    
    async def drain_stderr(self, stop_event: asyncio.Event) -> None:
        """No-op for compatibility with old PipeWire interface."""
        pass
