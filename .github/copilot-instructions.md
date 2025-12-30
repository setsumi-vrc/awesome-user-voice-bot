# TTS Server Project - AI Agent Instructions

## Architecture Overview
This is a real-time voice AI system with two FastAPI microservices:
- **STT Server** (`stt/server.py`): WebSocket-based speech-to-text using faster-whisper
- **TTS Server** (`tts/server.py`): HTTP API that processes text through local Ollama LLM, then converts responses to speech via Piper

**Project Structure:**
- `core/` - Shared modules (audio, config, llm, piper_client, model)
- `stt/` - Speech-to-text server and tests
- `tts/` - Text-to-speech server and tests
- `voices/` - Piper voice models (ONNX)

Data flow: Audio input → STT transcription → LLM processing → TTS synthesis → Audio output

## Key Components & Patterns

### Server Architecture
- Use FastAPI with uvicorn for both services
- STT runs on port 8010, TTS on port 8000
- STT uses WebSockets for real-time audio streaming with `BufferState` management
- TTS uses HTTP POST with Pydantic models and rate limiting via asyncio.Semaphore

### Configuration Management
- **Centralized**: `core/config.py` with `@lru_cache` for performance
- Loads from `config.yaml` or environment variables
- All settings accessible via `get_settings()` singleton

### Audio Processing (`core/audio.py`)
- PCM16LE audio format conversion to float32: `audio_i16.astype(np.float32) / 32768.0`
- RMS calculation for silence detection
- Silence detection using RMS threshold (`SILENCE_RMS_THRESHOLD = 0.008`)
- Minimum utterance duration: 0.35 seconds

### Whisper Model (`core/model.py`)
- GPU acceleration with fallback to CPU (`device="cuda"` with `compute_type="float16"`)
- Global model instance with `asyncio.Lock` for thread-safe access
- Lazy loading on startup

### LLM Integration (`core/llm.py`)
- Direct HTTP calls to local Ollama instance at `http://127.0.0.1:11434/api/generate`
- Model: "dagbs/darkidol-llama-3.1-8b-instruct-1.0-uncensored"
- System prompt loaded from file via `_load_system_prompt()`
- Response generation: temperature 0.3, max 120 tokens
- Retry logic with exponential backoff (3 attempts by default)

### TTS Synthesis (`core/piper_client.py`)
- Piper binary execution: `piper -m MODEL -c CONFIG -f output.wav`
- Voice models in `voices/` directory (ONNX format)
- Temporary WAV files with automatic cleanup
- **Validation**: Checks model/config existence before synthesis
- Default voice: `en_US-kusal-medium.onnx`

## Development Workflow

### Running Services
```bash
# STT Server
python -m uvicorn stt.server:app --host 0.0.0.0 --port 8010

# TTS Server
python -m uvicorn tts.server:app --host 0.0.0.0 --port 8000
```

### Voice Management
```bash
# Download voices
python -m piper.download_voices en_US-kusal-medium
```

### Testing
```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest stt/test_stt_server.py

# Run with coverage
python -m pytest --cov=.
```

## Project Conventions

### Path Handling
- Relative paths using `pathlib.Path` and `BASE_DIR`
- Configurable voice models and system prompt paths
- Automatic path resolution for cross-platform compatibility

### Error Handling
- WebSocket disconnections caught and handled gracefully
- LLM API timeouts: 30 seconds with fallback responses
- Piper subprocess errors return stderr in response
- File existence checks before voice synthesis

### Audio Constants
- Sample rate: 16000 Hz
- Silence detection: RMS threshold 0.008, max 0.7 seconds
- Language: hardcoded to "en"

### Code Style
- **BufferState dataclass** for managing STT audio buffer state
- **Message type constants** (MSG_TYPE_READY, MSG_TYPE_TRANSCRIPT, etc.)
- **Private helper functions** prefixed with `_` for internal logic
- **@lru_cache** on configuration loading for performance
- **Validation first** - check file existence before operations
- Extracted common functions to reduce duplication
- GPU acceleration with CPU fallback
- Proper exception handling with specific exception types
- Mocked dependencies in unit tests

## Integration Points
- Ollama API for text generation
- Piper TTS for voice synthesis
- WebSocket clients for real-time STT
- HTTP clients for TTS requests with voice selection

## Common Patterns
- Audio buffer accumulation during voice activity
- Forced flush via "flush" text message
- Transcript responses include duration metadata
- Error messages sent as JSON over WebSocket
- Unit tests with mocked external dependencies

## Recent Refactorings (Dec 2025)
- ✅ Eliminated 60+ lines of duplicate buffer reset code via BufferState
- ✅ Added configuration caching with @lru_cache
- ✅ Extracted _load_system_prompt() and _make_ollama_request() for testability
- ✅ Added file validation in piper_client before synthesis
- ✅ Improved logging consistency (logger.error with exc_info=True)
- ✅ Created message type constants to eliminate magic strings
- GPU acceleration with CPU fallback
- Proper exception handling with specific exception types
- Mocked dependencies in unit tests

## Integration Points
- Ollama API for text generation
- Piper TTS for voice synthesis
- WebSocket clients for real-time STT
- HTTP clients for TTS requests with voice selection

## Common Patterns
- Audio buffer accumulation during voice activity
- Forced flush via "flush" text message
- Transcript responses include duration metadata
- Error messages sent as JSON over WebSocket
- Unit tests with mocked external dependencies</content>
<parameter name="filePath">c:\tts_server\.github\copilot-instructions.md