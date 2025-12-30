import asyncio
import logging
from pathlib import Path
from io import BytesIO
from typing import Any
import requests

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from core.config import get_settings
from core.llm import generate_reply, LLMError, is_ollama_available
from core.piper_client import synthesize_text_to_wav, PiperError

# Initialize settings and logging
settings = get_settings()

# Configure logging level from settings
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.WARNING),
    format='%(levelname)s:     %(message)s'
)
logger = logging.getLogger(__name__)


# Health check log filter
class HealthCheckFilter(logging.Filter):
    """Filter out health check logs to reduce spam."""
    def filter(self, record: logging.LogRecord) -> bool:
        if settings.FILTER_HEALTH_LOGS:
            # Filter out uvicorn access logs for /health endpoint
            return 'GET /health' not in record.getMessage()
        return True


# Apply filter to uvicorn access logger
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(HealthCheckFilter())

app = FastAPI(title="TTS Server", description="Text-to-Speech API with LLM integration")

# Mount static files for frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Rate limiting: semaphore to limit concurrent TTS requests
_tts_semaphore = asyncio.Semaphore(settings.TTS_MAX_CONCURRENT)

# Default fallback response
DEFAULT_FALLBACK = "Sorry, can you repeat that?"

# Global runtime configuration (in-memory, can be changed via API)
class RuntimeConfig:
    def __init__(self):
        self.personality: str | None = None
        self.model: str = settings.OLLAMA_MODEL
        self.voice: str | None = None
        self.speaker_id: int = settings.PIPER_SPEAKER_ID
        self.length_scale: float = settings.PIPER_LENGTH_SCALE
        self.noise_scale: float = settings.PIPER_NOISE_SCALE
        self.noise_w: float = settings.PIPER_NOISE_W

runtime_config = RuntimeConfig()

# Conversation log (stored in memory)
conversation_log = []

# Prometheus metrics
tts_requests = Counter(
    'tts_requests_total',
    'Total number of TTS requests',
    ['status']
)
tts_duration = Histogram(
    'tts_request_duration_seconds',
    'Time spent processing TTS requests',
    ['stage']
)
llm_requests = Counter(
    'llm_requests_total',
    'Total number of LLM requests',
    ['status']
)


class TTSReq(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=settings.TTS_MAX_TEXT_LENGTH,
        description="Text to synthesize"
    )
    personality: str | None = Field(
        default=None,
        description="Personality name (system prompt file without .txt extension)"
    )
    model: str | None = Field(
        default=None,
        description="Ollama model name (e.g., 'llama2', 'mistral')"
    )
    voice: str | None = Field(
        default=None,
        description="Voice model name (e.g., 'en_US-glados-high')"
    )
    speaker_id: int | None = Field(
        default=None,
        ge=0,
        description="Speaker ID for multi-speaker models"
    )
    length_scale: float | None = Field(
        default=None,
        ge=0.1,
        le=2.0,
        description="Speech speed (1.0 = normal, <1.0 = faster, >1.0 = slower)"
    )
    noise_scale: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Voice variance/expressiveness"
    )
    noise_w: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Voice stability"
    )


class PersonalityContent(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        description="System prompt content"
    )


def _list_available_voices() -> list[str]:
    """List available voice files in voices directory.
    
    Returns:
        List of voice model names (without .onnx extension).
    """
    voices_dir = Path(settings.VOICES_DIR)
    if not voices_dir.exists():
        return []
    voices = [
        f.stem
        for f in voices_dir.glob("*.onnx")
        if not f.stem.endswith(".json")
    ]
    return voices


@app.get("/")
async def root():
    """Serve the frontend interface.
    
    Returns:
        HTML response with the frontend application.
    """
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return Response(content=html_content, media_type="text/html")


@app.get("/health")
def health() -> dict[str, bool | str]:
    """TTS health check: verify Ollama is available.
    
    Returns:
        Health status dictionary.
        
    Raises:
        HTTPException: If Ollama is unavailable.
    """
    ollama_ok = is_ollama_available()
    if not ollama_ok:
        logger.warning("Ollama health check failed")
        raise HTTPException(status_code=503, detail="Ollama unavailable")
    return {
        "status": "ok",
        "ollama": True,
    }


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus metrics endpoint.
    
    Returns:
        Prometheus metrics in text format.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/voices")
def get_voices() -> dict[str, list[str]]:
    """List available voice models.
    
    Returns:
        Dictionary with list of available voice model names.
    """
    voices = _list_available_voices()
    return {"voices": voices}


@app.get("/models")
def get_models() -> dict[str, Any]:
    """List available Ollama models.
    
    Returns:
        Dictionary with list of model names and current default model.
    """
    try:
        base_url = settings.OLLAMA_URL.replace("/api/generate", "")
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        models = [m["name"] for m in data.get("models", [])]
        
        return {
            "models": models,
            "current": runtime_config.model
        }
    except Exception as e:
        logger.error(f"Failed to fetch Ollama models: {e}")
        raise HTTPException(status_code=503, detail="Failed to fetch models from Ollama")


@app.get("/config")
def get_config() -> dict[str, Any]:
    """Get current runtime configuration.
    
    Returns:
        Current configuration values.
    """
    return {
        "personality": runtime_config.personality,
        "model": runtime_config.model,
        "voice": runtime_config.voice,
        "speaker_id": runtime_config.speaker_id,
        "length_scale": runtime_config.length_scale,
        "noise_scale": runtime_config.noise_scale,
        "noise_w": runtime_config.noise_w
    }


@app.post("/config")
def update_config(config: dict[str, Any]) -> dict[str, str]:
    """Update runtime configuration in memory.
    
    Args:
        config: Configuration values to update.
        
    Returns:
        Success message.
    """
    if "personality" in config:
        runtime_config.personality = config["personality"]
        logger.info(f"Updated personality: {runtime_config.personality}")
    
    if "model" in config:
        runtime_config.model = config["model"]
        logger.info(f"Updated model: {runtime_config.model}")
    
    if "voice" in config:
        runtime_config.voice = config["voice"]
        logger.info(f"Updated voice: {runtime_config.voice}")
    
    if "speaker_id" in config:
        runtime_config.speaker_id = int(config["speaker_id"])
        logger.info(f"Updated speaker_id: {runtime_config.speaker_id}")
    
    if "length_scale" in config:
        runtime_config.length_scale = float(config["length_scale"])
        logger.info(f"Updated length_scale: {runtime_config.length_scale}")
    
    if "noise_scale" in config:
        runtime_config.noise_scale = float(config["noise_scale"])
        logger.info(f"Updated noise_scale: {runtime_config.noise_scale}")
    
    if "noise_w" in config:
        runtime_config.noise_w = float(config["noise_w"])
        logger.info(f"Updated noise_w: {runtime_config.noise_w}")
    
    return {"message": "Configuration updated successfully"}


@app.get("/conversations")
def get_conversations(limit: int = 50) -> dict[str, Any]:
    """Get recent conversations.
    
    Args:
        limit: Maximum number of conversations to return.
        
    Returns:
        List of recent conversations.
    """
    return {
        "conversations": conversation_log[-limit:] if limit else conversation_log,
        "total": len(conversation_log)
    }


@app.delete("/conversations")
def clear_conversations() -> dict[str, str]:
    """Clear conversation log.
    
    Returns:
        Success message.
    """
    conversation_log.clear()
    logger.info("Conversation log cleared")
    return {"message": "Conversation log cleared"}


@app.post("/tts")
async def tts(req: TTSReq) -> StreamingResponse:
    """Synthesize text to speech with rate limiting.
    
    Args:
        req: TTS request containing text to synthesize.
        
    Returns:
        Streaming response with WAV audio data.
        
    Raises:
        HTTPException: If text is empty, LLM fails, or TTS fails.
    """
    import time
    start_time = time.time()
    
    user_text = req.text.strip()
    if not user_text:
        tts_requests.labels(status='invalid_input').inc()
        raise HTTPException(status_code=400, detail="empty text")
    
    # Acquire semaphore (rate limiting)
    async with _tts_semaphore:
        # Use runtime config as defaults if request doesn't specify
        personality = req.personality or runtime_config.personality
        model_name = req.model or runtime_config.model
        voice = req.voice or runtime_config.voice
        
        # Load personality if specified
        system_prompt = None
        if personality:
            personalities_dir = Path(__file__).parent.parent / "personalities"
            personality_file = personalities_dir / f"{personality}.txt"
            if personality_file.exists():
                try:
                    system_prompt = personality_file.read_text(encoding="utf-8").strip()
                    logger.info(f"Using personality: {personality}")
                except Exception as e:
                    logger.warning(f"Failed to load personality '{personality}': {e}")
        
        try:
            logger.info(f"Generating LLM reply for: {user_text[:50]}...")
            
            with tts_duration.labels(stage='llm').time():
                reply_text = generate_reply(
                    user_text, 
                    system_prompt=system_prompt,
                    model=model_name
                ) or DEFAULT_FALLBACK
                llm_requests.labels(status='success').inc()
                
        except LLMError as e:
            logger.error(f"LLM error: {e}")
            llm_requests.labels(status='error').inc()
            tts_requests.labels(status='llm_error').inc()
            raise HTTPException(status_code=503, detail=f"LLM unavailable: {e}")

        try:
            with tts_duration.labels(stage='synthesis').time():
                # Use runtime config as defaults for voice parameters
                voice_params = {}
                
                # Use voice from request or runtime config
                voice_to_use = voice
                if voice_to_use:
                    voice_model = Path(settings.VOICES_DIR) / f"{voice_to_use}.onnx"
                    voice_config = Path(settings.VOICES_DIR) / f"{voice_to_use}.onnx.json"
                    if voice_model.exists() and voice_config.exists():
                        voice_params['model_path'] = str(voice_model)
                        voice_params['config_path'] = str(voice_config)
                
                # Use request params or runtime config
                voice_params['speaker_id'] = req.speaker_id if req.speaker_id is not None else runtime_config.speaker_id
                voice_params['length_scale'] = req.length_scale if req.length_scale is not None else runtime_config.length_scale
                voice_params['noise_scale'] = req.noise_scale if req.noise_scale is not None else runtime_config.noise_scale
                voice_params['noise_w'] = req.noise_w if req.noise_w is not None else runtime_config.noise_w
                
                wav_bytes = synthesize_text_to_wav(reply_text, **voice_params)
        except PiperError as e:
            logger.error(f"Piper error: {e}")
            tts_requests.labels(status='piper_error').inc()
            raise HTTPException(status_code=502, detail=f"TTS backend failed: {e}")

        # Calculate total duration
        total_duration = time.time() - start_time
        
        logger.info(f"TTS complete: {len(wav_bytes)} bytes in {total_duration:.2f}s")
        tts_requests.labels(status='success').inc()
        
        # Add to conversation log
        import datetime
        conversation_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user_text": user_text,
            "bot_response": reply_text,
            "personality": personality,
            "model": model_name,
            "voice": voice_to_use,
            "duration": round(total_duration, 2)
        }
        conversation_log.append(conversation_entry)
        
        # Keep log size under control (0 = unlimited)
        if settings.MAX_CONVERSATION_LOG_ENTRIES > 0 and len(conversation_log) > settings.MAX_CONVERSATION_LOG_ENTRIES:
            conversation_log.pop(0)
        
        # Sanitize bot response for HTTP header (remove newlines, limit length)
        safe_reply = reply_text.replace('\n', ' ').replace('\r', '').strip()
        if len(safe_reply) > 500:
            safe_reply = safe_reply[:497] + "..."
        
        return StreamingResponse(
            BytesIO(wav_bytes),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=tts.wav",
                "X-Bot-Response": safe_reply
            }
        )


@app.get("/personalities")
def list_personalities() -> dict[str, list[str]]:
    """List available personality files.
    
    Returns:
        Dictionary with list of personality names (without .txt extension).
    """
    personalities_dir = Path(__file__).parent.parent / "personalities"
    if not personalities_dir.exists():
        return {"personalities": []}
    
    personalities = [
        f.stem
        for f in personalities_dir.glob("*.txt")
    ]
    return {"personalities": sorted(personalities)}


@app.get("/personalities/{name}")
def get_personality(name: str) -> PersonalityContent:
    """Get personality content by name.
    
    Args:
        name: Personality name (without .txt extension).
        
    Returns:
        Personality content.
        
    Raises:
        HTTPException: If personality file not found.
    """
    personalities_dir = Path(__file__).parent.parent / "personalities"
    personality_file = personalities_dir / f"{name}.txt"
    
    if not personality_file.exists():
        raise HTTPException(status_code=404, detail=f"Personality '{name}' not found")
    
    try:
        content = personality_file.read_text(encoding="utf-8")
        return PersonalityContent(content=content)
    except Exception as e:
        logger.error(f"Error reading personality file '{name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read personality: {str(e)}")


@app.post("/personalities/{name}")
def save_personality(name: str, data: PersonalityContent) -> dict[str, str]:
    """Save or create a personality file.
    
    Args:
        name: Personality name (without .txt extension).
        data: Personality content to save.
        
    Returns:
        Success message.
        
    Raises:
        HTTPException: If save fails or name contains invalid characters.
    """
    # Validate filename (prevent path traversal)
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid personality name")
    
    personalities_dir = Path(__file__).parent.parent / "personalities"
    personalities_dir.mkdir(exist_ok=True)
    
    personality_file = personalities_dir / f"{name}.txt"
    
    try:
        personality_file.write_text(data.content, encoding="utf-8")
        logger.info(f"Saved personality '{name}'")
        return {"message": f"Personality '{name}' saved successfully"}
    except Exception as e:
        logger.error(f"Error saving personality '{name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save personality: {str(e)}")
