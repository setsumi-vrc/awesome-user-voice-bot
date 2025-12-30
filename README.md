TTS Server
==========

Real-time voice AI system with two FastAPI microservices:
- **STT Server** (port 8010): WebSocket-based speech-to-text using faster-whisper
- **TTS Server** (port 8000): HTTP API with Ollama LLM + Piper TTS synthesis
- **Web Frontend**: Modern web interface for testing and monitoring

**Status**: ✅ Version 2.0 - Production-ready with optimizations (see [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md))

Architecture
- `core/` - Shared utilities: `config.py` (YAML-based + env fallback), `audio.py`, `model.py`, `llm.py` (with retry logic), `piper_client.py`, `logger.py` (structured logging)
- `stt/` - STT service: WebSocket `/ws/stt`, health check `/health`
- `tts/` - TTS service: HTTP `/tts`, health check `/health`, voice listing `/voices`
- `frontend/` - Web interface: HTML/CSS/JS for testing TTS and monitoring metrics
- `run_services.py` - Launcher with graceful shutdown
- `config.yaml` - Development configuration (YAML-first design)
- `config.prod.yaml` - Production hardening (smaller models, JSON logs, lower concurrency)

Quick Start
-----------

### Prerequisites

- **Python 3.10+**
- **Ollama** with LLM model installed (for text generation)
- **Piper TTS** executable (for voice synthesis) - [Installation Guide](PIPER_INSTALLATION.md)

### Installation

1. Setup virtualenv and install dependencies:

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

2. Install Piper TTS:

**Windows:**
```powershell
# Download from https://github.com/rhasspy/piper/releases
# Extract piper.exe and add to PATH, or set full path in config.yaml
```

**Linux/macOS:**
```bash
pip install piper-tts
```

See [PIPER_INSTALLATION.md](PIPER_INSTALLATION.md) for detailed instructions.

3. Verify configuration:

```bash
python -c "from core.config import get_settings; s = get_settings(); print(f'✅ Loaded: {s.ENVIRONMENT}')"
```

4. Run both services:

```bash
# Development (plaintext logs, lighter models)
python run_services.py

# Production (JSON logs, production config)
CONFIG_PATH=config.prod.yaml python run_services.py

# Or run individually:
uvicorn stt.server:app --host 0.0.0.0 --port 8010
uvicorn tts.server:app --host 0.0.0.0 --port 8000
```

5. Access the web interface:

```
http://localhost:8000
```

The frontend provides:
- 💬 Text-to-speech generation with voice selection
- 📊 Real-time metrics and service health monitoring
- ⚙️ Configuration display
- 📚 API documentation

See [frontend/README.md](frontend/README.md) for detailed frontend documentation.

6. Health Check:

```bash
curl http://localhost:8010/health
curl http://localhost:8000/health
```

Configuration
-------------

Settings are loaded in order (last wins):
1. **Defaults** in `core/config.py`
2. **config.yaml** in repo root (if exists)
3. **Environment variables** (e.g., `OLLAMA_URL=...`)

Common settings:
```yaml
# Audio
sample_rate: 16000
max_utterance_seconds: 12.0
max_buffer_seconds: 120.0

# Models
whisper_model_name: small        # tiny, base, small, medium, large
whisper_device: cuda             # cuda, cpu
ollama_model: dagbs/darkidol-llama-3.1-8b-instruct-1.0-uncensored

# Resilience
ollama_retry_attempts: 3         # Retries with exponential backoff
tts_max_concurrent: 4            # Rate limiting

# Logging
log_json_mode: false             # true for production
environment: development         # development, staging, production
```

See [config.yaml](config.yaml) and [config.prod.yaml](config.prod.yaml) for all keys.

Endpoints
---------

### STT Server (port 8010)

**WebSocket `/ws/stt`**: Real-time speech-to-text
```
Client → Binary audio (PCM16LE, 16kHz)
Server ← JSON: {"type": "transcript", "text": "...", "duration": 1.23, "keep_open": true}
Server ← JSON: {"type": "buffer_limit_reached", "duration": 120.0}  # if exceeds limit
```

**GET `/health`**: Health check
```json
{"status": "ok", "whisper_loaded": true, "environment": "development"}
```

### TTS Server (port 8000)

**POST `/tts`**: Text-to-speech synthesis
```bash
curl -X POST http://localhost:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "en_US-kusal-medium"}'
  
# Response: audio/wav stream
```

**GET `/health`**: Health check
```json
{"status": "ok", "ollama": true, "environment": "development"}
```

**GET `/voices`**: List available voices
```json
{"voices": ["en_US-kusal-medium", "en_US-ryan-high"], "default": "en_US-kusal-medium"}
```

Features (v2.0)
----------------

✅ **Resilience**
- Retry logic with exponential backoff for Ollama
- Graceful shutdown (SIGTERM → 10s grace period)
- Health checks for both services

✅ **Performance**
- In-memory TTS (no disk I/O)
- Rate limiting (configurable concurrent requests)
- Buffer feedback in STT (client knows when audio is truncated)

✅ **Reliability**
- Structured JSON logging for production
- Request validation (max text length)
- CUDA auto-detection (Windows)

✅ **Flexibility**
- Multi-voice support via `/voices` endpoint
- Environment-aware config (dev/staging/prod)
- YAML-first configuration

Testing
-------

Run all tests:
```bash
pytest
```

Test specific service:
```bash
pytest test_stt_server.py -v
pytest test_tts_server.py -v
```

Deployment
----------

### Systemd (Linux)

```ini
[Unit]
Description=TTS Server
After=network.target

[Service]
Type=simple
User=tts
WorkingDirectory=/opt/tts_server
Environment="CONFIG_PATH=/opt/tts_server/config.prod.yaml"
Environment="ENVIRONMENT=production"
ExecStart=/opt/tts_server/.venv/bin/python run_services.py
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt

# Optional: Copy ONNX voice models
# COPY voices/ /app/voices/

EXPOSE 8000 8010
ENV CONFIG_PATH=/app/config.prod.yaml
ENV ENVIRONMENT=production
CMD ["python", "run_services.py"]
```

Build and run:
```bash
docker build -t tts-server .
docker run -p 8000:8000 -p 8010:8010 tts-server
```

Monitoring
----------

Health check loop:
```bash
while true; do
  echo "STT: $(curl -s http://localhost:8010/health | jq .whisper_loaded)"
  echo "TTS: $(curl -s http://localhost:8000/health | jq .ollama)"
  sleep 5
done
```

Log monitoring (production JSON logs):
```bash
tail -f /var/log/tts_server.log | jq '.level, .message'
```

Troubleshooting
---------------

**STT WebSocket closes immediately**
- Check `GET /health` → `whisper_loaded` is `true`
- Verify CUDA paths auto-detected (Windows): Look for `Added CUDA path:` in logs

**TTS returns 503**
- Check Ollama: `curl http://localhost:11434/api/tags`
- Retry logic will attempt 3x with backoff (default 1s, 2s, 4s)

**Rate limiting (TTS slow)**
- `tts_max_concurrent: 4` by default (8 in production)
- Requests queue automatically; check logs for `"message": "TTS concurrent limit"`

**Graceful shutdown hangs**
- Services wait up to 10 seconds
- Force kill: `kill -9 <pid>`

Documentation
--------------

- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Overview of v2.0 improvements
- [README.IMPROVEMENTS.md](README.IMPROVEMENTS.md) - Detailed breakdown of all 16 optimizations
- [VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md) - Comprehensive validation checklist
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Developer reference

License & Attribution
---------------------

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Whisper (faster-whisper)](https://github.com/guillaumekln/faster-whisper) - Speech-to-text
- [Ollama](https://ollama.ai/) - Local LLM
- [Piper](https://github.com/rhasspy/piper) - Text-to-speech

