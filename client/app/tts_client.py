"""TTS client for generating bot responses."""
import logging

import requests

logger = logging.getLogger(__name__)


class TTSClient:
    """Client for TTS API requests with connection reuse."""
    
    def __init__(self, tts_url: str):
        """Initialize TTS client.
        
        Args:
            tts_url: Base URL for TTS endpoint.
        """
        self.url = tts_url
        self.session = requests.Session()
    
    def generate_speech(self, text: str) -> bytes:
        """Generate speech from text.
        
        Args:
            text: Text to synthesize.
            
        Returns:
            WAV audio bytes.
            
        Raises:
            requests.HTTPError: If request fails.
        """
        payload = {"text": text}
        
        logger.debug(f"TTS request: {payload}")
        
        response = self.session.post(
            self.url,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        
        return response.content
    
    def close(self) -> None:
        """Close session and cleanup resources."""
        self.session.close()
