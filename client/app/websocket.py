"""WebSocket handler for STT communication."""
import asyncio
import json
import logging
import time
from contextlib import suppress
from typing import Optional

import websockets
from websockets.legacy.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from app.audio import pcm16le_to_rms, create_silence_frame, play_wav_file
from app.config import Config
from app.metrics import Metrics
from app.tts_client import TTSClient
from app.vad import VADState

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Manages STT WebSocket connection and audio/transcript processing."""
    
    def __init__(
        self,
        config: Config,
        audio_queue: asyncio.Queue[bytes],
        tts_client: TTSClient,
        metrics: Metrics,
        stop_event: asyncio.Event
    ):
        self.config = config
        self.audio_queue = audio_queue
        self.tts_client = tts_client
        self.metrics = metrics
        self.stop_event = stop_event
        
        # Response cooldown tracking
        self.last_response_time = 0.0
        self.response_lock = asyncio.Lock()
    
    async def connect_and_run(self) -> None:
        """Connect to WebSocket and run sender/receiver tasks."""
        ws_config = self.config.websocket
        
        async with websockets.connect(
            self.config.server.stt_ws_url,
            max_size=ws_config.max_size,
            ping_interval=ws_config.ping_interval,
            ping_timeout=ws_config.ping_timeout,
            close_timeout=2.0,
            max_queue=ws_config.max_queue,
            write_limit=ws_config.write_limit,
        ) as ws:
            # Wait for ready message
            await self._wait_for_ready(ws)
            
            # Create and run sender/receiver tasks
            tasks = [
                asyncio.create_task(self._sender_task(ws), name="sender"),
                asyncio.create_task(self._receiver_task(ws), name="receiver"),
            ]
            
            # Wait for first exception
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_EXCEPTION
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            
            # Re-raise exception if any
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
    
    async def _wait_for_ready(self, ws: WebSocketClientProtocol) -> None:
        """Wait for server ready message.
        
        Args:
            ws: WebSocket connection.
        """
        try:
            ready_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            logger.info(f"STT server ready: {ready_msg}")
        except asyncio.TimeoutError:
            logger.warning("No ready message from STT server")
    
    async def _sender_task(self, ws: WebSocketClientProtocol) -> None:
        """Send audio chunks to STT server with VAD.
        
        Args:
            ws: WebSocket connection.
        """
        vad = VADState(
            silence_threshold=self.config.vad.silence_rms_threshold,
            silence_max_seconds=self.config.vad.silence_max_seconds,
            min_utterance_seconds=self.config.vad.min_utterance_seconds,
            utterance_cooldown=self.config.vad.utterance_cooldown
        )
        
        silence = create_silence_frame(self.config.audio.bytes_per_chunk)
        
        try:
            while not self.stop_event.is_set():
                # Get audio chunk with timeout
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_queue.get(),
                        timeout=self.config.queue.get_timeout
                    )
                except asyncio.TimeoutError:
                    continue
                
                now = time.monotonic()
                rms = pcm16le_to_rms(chunk)
                
                # VAD logic
                if not vad.in_utterance:
                    # Start utterance if voice detected and cooldown passed
                    if rms >= vad.silence_threshold and vad.can_start_utterance(now):
                        vad.start_utterance(now)
                        logger.debug("Utterance started")
                    else:
                        continue  # Skip silence outside utterance
                
                # Update voice activity timestamp if voice detected
                if rms >= vad.silence_threshold:
                    vad.update_voice_activity(now)
                
                # Send chunk to server
                await ws.send(chunk)
                
                # Check if utterance should end
                if vad.should_end_utterance(now):
                    duration = vad.end_utterance(time.monotonic())
                    
                    # Send silence tail to ensure server processes final audio
                    for _ in range(self.config.vad.silence_tail_frames):
                        await ws.send(silence)
                    
                    if vad.is_utterance_valid(duration):
                        logger.debug(f"Utterance ended ({duration:.2f}s)")
                    else:
                        logger.debug(f"Utterance too short ({duration:.2f}s), ignored")
        
        except (ConnectionClosed, ConnectionClosedError):
            self.stop_event.set()
            raise
        except Exception as e:
            logger.error(f"Sender error: {e}", exc_info=True)
            self.stop_event.set()
            raise
    
    async def _receiver_task(self, ws: WebSocketClientProtocol) -> None:
        """Receive transcripts and generate responses.
        
        Args:
            ws: WebSocket connection.
        """
        try:
            while not self.stop_event.is_set():
                raw_msg = await ws.recv()
                
                # Ignore binary messages
                if isinstance(raw_msg, (bytes, bytearray)):
                    continue
                
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")
                
                if msg_type == "transcript":
                    transcript_start = time.monotonic()
                    await self._handle_transcript(msg, transcript_start)
                
                elif msg_type == "error":
                    error_detail = msg.get("detail", "unknown error")
                    logger.error(f"STT server error: {error_detail}")
                    self.metrics.record_stt_error()
                    raise RuntimeError(f"STT error: {error_detail}")
        
        except (ConnectionClosed, ConnectionClosedError):
            self.stop_event.set()
            raise
        except Exception as e:
            logger.error(f"Receiver error: {e}", exc_info=True)
            self.stop_event.set()
            raise
    
    async def _handle_transcript(self, msg: dict, transcript_start: float) -> None:
        """Process transcript and generate response.
        
        Args:
            msg: Transcript message from server.
            transcript_start: Timestamp when transcript was received.
        """
        text = (msg.get("text") or "").strip()
        if not text:
            return
        
        # Calculate STT latency
        stt_duration = msg.get("duration", 0.0)
        self.metrics.record_transcription(stt_duration)
        
        logger.info(f"🎤 Heard: {text} ({stt_duration:.2f}s)")
        
        # Check response cooldown
        now = time.monotonic()
        if (now - self.last_response_time) < self.config.response.cooldown_seconds:
            logger.debug("Response skipped (cooldown)")
            self.metrics.record_skip()
            return
        
        # Generate and play response
        async with self.response_lock:
            # Double-check cooldown after acquiring lock
            now = time.monotonic()
            if (now - self.last_response_time) < self.config.response.cooldown_seconds:
                self.metrics.record_skip()
                return
            
            try:
                # Generate speech (blocking, run in thread)
                tts_start = time.monotonic()
                wav_bytes = await asyncio.to_thread(
                    self.tts_client.generate_speech,
                    text
                )
                tts_duration = time.monotonic() - tts_start
                
                # Play audio
                await play_wav_file(wav_bytes, self.config.audio.output_device)
                
                # Update metrics
                e2e_duration = time.monotonic() - transcript_start
                self.metrics.record_response(tts_duration, e2e_duration)
                self.last_response_time = time.monotonic()
                
                logger.info(
                    f"🤖 Response: TTS {tts_duration:.2f}s, E2E {e2e_duration:.2f}s"
                )
            
            except Exception as e:
                logger.error(f"TTS error: {e}", exc_info=True)
                self.metrics.record_tts_error()
