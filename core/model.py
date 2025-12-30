import traceback
import asyncio
from typing import Optional
from faster_whisper import WhisperModel

from .config import get_settings

settings = get_settings()

# Global model instance and lock for serialized GPU access
model: Optional[WhisperModel] = None
model_lock = asyncio.Lock()


def load_model() -> WhisperModel:
    """Initialize and store the Whisper model in this module.
    
    Returns:
        The loaded Whisper model instance.
        
    Raises:
        Exception: If model loading fails.
    """
    global model
    try:
        m = WhisperModel(
            settings.WHISPER_MODEL_NAME,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        model = m
        return model
    except Exception:
        traceback.print_exc()
        raise
