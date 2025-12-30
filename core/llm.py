import requests
import time
import logging
from pathlib import Path
from typing import Optional
from pybreaker import CircuitBreaker, CircuitBreakerError, CircuitBreakerListener

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMError(Exception):
    """Exception raised when LLM operations fail."""
    pass


class OllamaCircuitBreakerListener(CircuitBreakerListener):
    """Custom listener for circuit breaker state changes."""
    
    def state_change(self, cb: CircuitBreaker, old_state, new_state) -> None:
        """Log circuit breaker state changes."""
        logger.warning(
            f"Circuit breaker '{cb.name}' state changed: {old_state.name} -> {new_state.name}"
        )


# Initialize circuit breaker with configuration
_circuit_breaker: Optional[CircuitBreaker] = None

if settings.CIRCUIT_BREAKER_ENABLED:
    _circuit_breaker = CircuitBreaker(
        fail_max=settings.CIRCUIT_BREAKER_FAIL_MAX,
        reset_timeout=settings.CIRCUIT_BREAKER_RESET_TIMEOUT,
        name='ollama_circuit_breaker',
        listeners=[OllamaCircuitBreakerListener()]
    )


def is_ollama_available() -> bool:
    """Check if Ollama is reachable and has models available."""
    try:
        # Extract base URL properly (remove /api/generate, add /api/tags)
        base_url = settings.OLLAMA_URL.replace("/api/generate", "")
        url = f"{base_url}/api/tags"
        r = requests.get(url, timeout=2)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def generate_reply(user_text: str, system_prompt: str | None = None, model: str | None = None) -> str:
    """Generate reply using Ollama with retry logic and circuit breaker.
    
    Args:
        user_text: The user's input text to generate a reply for.
        system_prompt: Optional custom system prompt. If None, loads from default file.
        model: Optional Ollama model name. If None, uses default from settings.
        
    Returns:
        Generated response text from the LLM.
        
    Raises:
        LLMError: If the LLM is unavailable after all retries or circuit is open.
    """
    user_text = user_text.strip()
    if not user_text:
        logger.warning("Empty user text provided")
        return ""

    # Load system prompt (use custom or default)
    prompt = system_prompt if system_prompt is not None else _load_system_prompt()
    prompt = f"{prompt}\n\nUser: {user_text}\nAssistant:"
    
    # Use custom model or default from settings
    model_name = model or settings.OLLAMA_MODEL

    # Try to use circuit breaker if enabled
    if _circuit_breaker is not None:
        try:
            return _generate_with_circuit_breaker(prompt, model_name)
        except CircuitBreakerError as e:
            logger.error(f"Circuit breaker is open: {e}")
            raise LLMError("Service temporarily unavailable (circuit breaker open)")
    else:
        return _generate_with_retry(prompt, model_name)


def _generate_with_circuit_breaker(prompt: str, model: str) -> str:
    """Generate reply using circuit breaker protection.
    
    Args:
        prompt: The prompt to send to Ollama.
        model: The Ollama model name to use.
        
    Returns:
        Generated response text.
        
    Raises:
        LLMError: If the request fails.
    """
    @_circuit_breaker
    def _call_ollama() -> str:
        try:
            return _make_ollama_request(prompt, model)
        except requests.exceptions.RequestException:
            # Let circuit breaker count this failure
            raise
    
    try:
        return _call_ollama()
    except requests.exceptions.RequestException as e:
        # Convert to LLMError for consistent error handling
        logger.error(f"Ollama request failed: {e}")
        raise LLMError(str(e)) from e


def _generate_with_retry(prompt: str) -> str:
    """Generate reply with retry logic (no circuit breaker)."""
    # Retry logic with exponential backoff
def _generate_with_retry(prompt: str, model: str) -> str:
    """Generate reply with retry logic (no circuit breaker)."""
    # Retry logic with exponential backoff
    for attempt in range(settings.OLLAMA_RETRY_ATTEMPTS):
        try:
            response_text = _make_ollama_request(prompt, model)
            logger.info(f"Ollama generated reply ({len(response_text)} chars)")
            return response_text
        except requests.exceptions.RequestException as e:
            if attempt < settings.OLLAMA_RETRY_ATTEMPTS - 1:
                wait_time = settings.OLLAMA_RETRY_BACKOFF * (2 ** attempt)
                logger.warning(
                    f"Ollama request failed (attempt {attempt + 1}/{settings.OLLAMA_RETRY_ATTEMPTS}). "
                    f"Retrying in {wait_time:.1f}s: {e}"
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Ollama unavailable after {settings.OLLAMA_RETRY_ATTEMPTS} attempts: {e}")
                raise LLMError(str(e))
    
    # Should never reach here but for type safety
    raise LLMError("Max retries exceeded")


def _load_system_prompt() -> str:
    """Load system prompt from file."""
    try:
        spath = settings.SYSTEM_PROMPT_PATH
        if spath and Path(spath).exists():
            return Path(spath).read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning(f"Failed to load system prompt: {e}")
    return ""


def _make_ollama_request(prompt: str, model: str) -> str:
    """Make HTTP request to Ollama API."""
    r = requests.post(
        settings.OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 120},
        },
        timeout=settings.OLLAMA_TIMEOUT,
    )
    r.raise_for_status()
    return (r.json().get("response") or "").strip()
