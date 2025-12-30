import asyncio
import time
import logging
import contextlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from core.config import get_settings
from core.dlls import setup_cuda_paths

settings = get_settings()
setup_cuda_paths(settings.CUDA_X64_PATH, settings.CUDNN_BIN_PATH, verify=True)

# Import CUDA stuff after setup
import core.model as model_module
from core.audio import pcm16le_to_float32, rms

logger = logging.getLogger(__name__)

# Prometheus metrics
transcription_requests = Counter(
    'stt_transcription_requests_total',
    'Total number of transcription requests'
)
transcription_duration = Histogram(
    'stt_transcription_duration_seconds',
    'Time spent on transcription'
)
websocket_connections = Counter(
    'stt_websocket_connections_total',
    'Total WebSocket connections',
    ['status']
)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan: startup and shutdown."""
    # Startup
    model_module.load_model()
    logger.info("Whisper model loaded successfully")
    yield
    # Shutdown (if needed)
    logger.info("Shutting down STT server")

app = FastAPI(lifespan=lifespan)

# Add CORS middleware for health checks from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
SAMPLE_RATE = settings.SAMPLE_RATE
SILENCE_RMS_THRESHOLD = settings.SILENCE_RMS_THRESHOLD
SILENCE_MAX_SECONDS = settings.SILENCE_MAX_SECONDS
MIN_UTTERANCE_SECONDS = settings.MIN_UTTERANCE_SECONDS
MAX_UTTERANCE_SECONDS = settings.MAX_UTTERANCE_SECONDS
MAX_BUFFER_SECONDS = settings.MAX_BUFFER_SECONDS

WHISPER_LANG = settings.WHISPER_LANG
WHISPER_BEAM = settings.WHISPER_BEAM

# WebSocket message types
MSG_TYPE_READY = "ready"
MSG_TYPE_TRANSCRIPT = "transcript"
MSG_TYPE_FLUSHED = "flushed"
MSG_TYPE_ERROR = "error"


@dataclass
class BufferState:
    """Manage audio buffer state."""
    buf: bytearray
    started: bool = False
    utt_start_t: float | None = None
    last_voice_t: float | None = None
    total_buffered: float = 0.0

    def reset(self):
        """Reset buffer to initial state."""
        self.buf.clear()
        self.started = False
        self.utt_start_t = None
        self.last_voice_t = None
        self.total_buffered = 0.0

@app.get("/health")
def health() -> dict[str, bool | str]:
    """Health check endpoint."""
    return {"status": "ok", "whisper_loaded": model_module.model is not None}

@app.get("/metrics")
def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

def _transcribe_blocking(audio_f32: list[float]) -> str:
    """Transcribe audio using Whisper model (blocking operation)."""
    segments, _ = model_module.model.transcribe(
        audio_f32,
        language=WHISPER_LANG,
        beam_size=WHISPER_BEAM,
    )
    return "".join(seg.text for seg in segments).strip()

async def process_buffer(ws: WebSocket, state: BufferState) -> None:
    """Process accumulated audio buffer and send transcript."""
    utter_duration = (len(state.buf) / 2) / SAMPLE_RATE
    if utter_duration < MIN_UTTERANCE_SECONDS:
        return

    audio = pcm16le_to_float32(bytes(state.buf))
    
    transcription_requests.inc()
    with transcription_duration.time():
        async with model_module.model_lock:
            text = await asyncio.to_thread(_transcribe_blocking, audio)

    if text:
        await ws.send_json({
            "type": MSG_TYPE_TRANSCRIPT,
            "text": text,
            "duration": utter_duration
        })

@app.websocket("/ws/stt")
async def ws_stt(ws: WebSocket) -> None:
    """WebSocket endpoint for real-time speech-to-text."""
    await ws.accept()
    websocket_connections.labels(status='accepted').inc()
    
    if model_module.model is None:
        await ws.close(code=1011)
        websocket_connections.labels(status='model_not_loaded').inc()
        return

    state = BufferState(buf=bytearray())

    try:
        await ws.send_json({"type": MSG_TYPE_READY, "sr": SAMPLE_RATE})

        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("type") != "websocket.receive":
                continue

            if msg.get("bytes") is not None:
                chunk = msg["bytes"]
                if not chunk:
                    continue

                now = time.monotonic()
                level = rms(pcm16le_to_float32(chunk))
                dur = (len(chunk) / 2) / SAMPLE_RATE

                if not state.started:
                    if level >= SILENCE_RMS_THRESHOLD:
                        state.started = True
                        state.utt_start_t = now
                        state.last_voice_t = now
                        state.buf.extend(chunk)
                        state.total_buffered = dur
                    else:
                        continue
                else:
                    state.buf.extend(chunk)
                    state.total_buffered += dur
                    if level >= SILENCE_RMS_THRESHOLD:
                        state.last_voice_t = now

                    # Check buffer limits
                    if state.total_buffered >= MAX_BUFFER_SECONDS:
                        await process_buffer(ws, state)
                        state.reset()
                        continue

                    if state.utt_start_t is not None and (now - state.utt_start_t) >= MAX_UTTERANCE_SECONDS:
                        await process_buffer(ws, state)
                        state.reset()
                        continue

                    if (state.last_voice_t is not None and 
                        (now - state.last_voice_t) >= SILENCE_MAX_SECONDS and 
                        len(state.buf) > 0):
                        await process_buffer(ws, state)
                        state.reset()

            elif msg.get("text") is not None:
                text = (msg["text"] or "").strip().lower()
                if text == "flush" and len(state.buf) > 0:
                    await process_buffer(ws, state)
                    await ws.send_json({"type": MSG_TYPE_FLUSHED})
                    state.reset()

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        websocket_connections.labels(status='error').inc()
        with contextlib.suppress(Exception):
            await ws.send_json({"type": MSG_TYPE_ERROR, "detail": str(e)})
        with contextlib.suppress(Exception):
            await ws.close(code=1011)
