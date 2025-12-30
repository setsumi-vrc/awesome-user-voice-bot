# VRChat Talkback Bot Client

Real-time voice interaction client for VRChat. Captures game audio, transcribes via STT WebSocket server, and generates TTS responses using LLM.

## Features

- ✅ **Cross-platform**: Works on Windows and Linux
- ✅ **Low latency**: 20ms audio chunks for real-time conversation
- ✅ **Voice Activity Detection**: Automatic speech detection with configurable thresholds
- ✅ **Metrics tracking**: Monitor STT/TTS latency, response times, and error rates
- ✅ **Virtual audio support**: Capture from VB-Cable (Windows) or PipeWire (Linux)
- ✅ **Modular architecture**: Clean separation of concerns with type hints

## Architecture

```
client/
├── config.yaml           # Configuration file
├── client.py             # Main entry point
├── example.py            # Usage example
├── requirements.txt      # Dependencies
├── README.md             # This file
└── app/                  # Core package
    ├── __init__.py       # Package exports
    ├── config.py         # Configuration management
    ├── audio.py          # Audio capture (sounddevice)
    ├── vad.py            # Voice Activity Detection
    ├── tts_client.py     # TTS API client
    ├── websocket.py      # WebSocket handler
    └── metrics.py        # Performance tracking
```

## Prerequisites

### Windows

1. **Python 3.10+**
2. **Virtual Audio Cable** (to capture VRChat audio):
   - Download [VB-Audio Virtual Cable](https://vb-audio.com/Cable/)
   - Install and reboot
   - In VRChat audio settings: Output to "CABLE Input"
   - In Windows Sound settings: Set "CABLE Output" as recording device

### Linux

1. **Python 3.10+**
2. **PipeWire** (modern Linux audio server):
   ```bash
   # Ubuntu/Debian
   sudo apt install pipewire pipewire-pulse
   
   # Arch Linux
   sudo pacman -S pipewire pipewire-pulse
   ```

3. **Create virtual audio sinks** for VRChat:
   ```bash
   # Create monitoring sink for game audio
   pactl load-module module-null-sink sink_name=game_sink sink_properties=device.description="VRChat_Audio"
   
   # Route VRChat audio to this sink
   # Use pavucontrol or helvum to connect VRChat output to game_sink
   ```

## Installation

### 1. Clone repository

```bash
cd /path/to/tts_server/client
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

**Dependencies:**
- `numpy` - Audio RMS calculation
- `requests` - HTTP client for TTS
- `websockets` - STT WebSocket client
- `pyyaml` - Configuration parsing
- `sounddevice` - Cross-platform audio capture

### 3. Configure the client

Edit `config.yaml`:

```yaml
# Server endpoints
server:
  pc_ip: "192.168.1.150"  # Change to your server IP
  stt_port: 8010
  tts_port: 8000

# Audio settings
audio:
  sample_rate: 16000
  chunk_ms: 20
  input_device: "CABLE Output"  # Windows: "CABLE Output", Linux: "VRChat", or null for default
  output_device: null            # null = use default output

# Voice Activity Detection
vad:
  silence_rms_threshold: 0.008   # Lower = more sensitive
  silence_max_seconds: 0.7       # Max silence before utterance ends
  min_utterance_seconds: 0.35    # Minimum speech duration
  utterance_cooldown: 1.2        # Delay between utterances
  silence_tail_frames: 6         # Silence frames to send at end

# Response behavior
response:
  cooldown_seconds: 0.8          # Delay between bot responses

# Metrics
metrics:
  enabled: true
  log_interval: 30.0             # Log metrics every N seconds

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
```

## Configuration Guide

### Audio Device Selection

**To list available devices:**

```python
import sounddevice as sd
print(sd.query_devices())
```

**Windows example:**
```
[0] Microsoft Sound Mapper - Input
[1] CABLE Output (VB-Audio Virtual Cable)  ← Use this for VRChat
[2] Microphone Array (Built-in)
```

Set `input_device: "CABLE Output"` in config.yaml.

**Linux example:**
```
[0] Default
[1] Monitor of VRChat_Audio  ← Use this
[2] Built-in Audio Analog Stereo
```

Set `input_device: "VRChat"` (substring match) or `input_device: "Monitor of VRChat_Audio"`.

### VAD Tuning

**Adjust for your environment:**

- **Too sensitive** (bot triggers on noise):
  - Increase `silence_rms_threshold` (e.g., 0.012)
  - Increase `min_utterance_seconds` (e.g., 0.5)

- **Not sensitive enough** (misses speech):
  - Decrease `silence_rms_threshold` (e.g., 0.005)
  - Decrease `silence_max_seconds` (e.g., 0.5)

**Test with this command:**
```bash
# Enable DEBUG logging to see RMS values
python client.py  # Watch "RMS: 0.XXX" in logs
```

## Usage

### Basic Usage

```bash
cd /path/to/tts_server/client
python client.py
```

**Expected output:**
```
🚀 Talkback bot starting...
STT: ws://192.168.1.150:8010/ws/stt
TTS: http://192.168.1.150:8000/tts
Available input devices:
  [0] Default
  [1] CABLE Output (VB-Audio Virtual Cable) (2 ch)
✓ Selected device: [1] CABLE Output (VB-Audio Virtual Cable)
🎧 Starting audio capture: CABLE Output @ 16000Hz, 20ms chunks
🎤 Heard: hello there (0.82s)
🤖 Response: TTS 1.15s, E2E 1.97s
```

### Custom Configuration

```bash
python client.py --config my_config.yaml
```

Or use the example script:

```python
# example.py
from pathlib import Path
from client import TalkbackClient

client = TalkbackClient(config_path=Path("my_config.yaml"))
await client.run_with_reconnect()
```

### Running as Background Service

**Linux (systemd):**

Create `/etc/systemd/system/vrchat-bot.service`:

```ini
[Unit]
Description=VRChat Talkback Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/tts_server/client
ExecStart=/usr/bin/python3 /path/to/tts_server/client/client.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable vrchat-bot
sudo systemctl start vrchat-bot
sudo journalctl -u vrchat-bot -f  # View logs
```

**Windows (Task Scheduler):**

1. Open Task Scheduler
2. Create Basic Task → Name: "VRChat Bot"
3. Trigger: At startup
4. Action: Start a program
   - Program: `pythonw.exe` (no console window)
   - Arguments: `C:\path\to\tts_server\client\client.py`
   - Start in: `C:\path\to\tts_server\client`
5. Settings: Restart on failure

## Troubleshooting

### "Device not found" error

**Symptom**: `Device 'CABLE Output' not found, using default input`

**Solution:**
1. List devices: `python -c "import sounddevice as sd; print(sd.query_devices())"`
2. Find your virtual audio device name
3. Update `input_device` in config.yaml with exact substring

### No audio captured

**Windows:**
- Verify VB-Cable is set as recording device in Sound settings
- Check VRChat output is set to "CABLE Input"
- Test with: `python -c "import sounddevice as sd; print(sd.rec(16000, samplerate=16000))"`

**Linux:**
- Check PipeWire connections: `pw-link -io`
- Verify game audio routes to monitor sink
- Use `helvum` GUI to visualize connections

### High latency

**Symptoms**: Delayed responses, audio stuttering

**Solutions:**
1. Reduce `chunk_ms` to 10ms (config.yaml)
2. Lower `queue.max_size` to 50
3. Check network latency to server
4. Verify server is on local network (not cloud)

### Bot talks over players

**Symptom**: Bot responds before player finishes speaking

**Solution:**
- Increase `response.cooldown_seconds` (e.g., 1.5)
- Increase `vad.silence_max_seconds` (e.g., 1.0)

### WebSocket connection fails

**Symptom**: `ConnectionRefusedError` or `ConnectionClosedError`

**Solutions:**
1. Verify server is running: `curl http://<server_ip>:8000/health`
2. Check firewall allows ports 8000 and 8010
3. Verify `pc_ip` in config.yaml is correct
4. Check server logs for errors

### Audio drops / buffer overruns

**Symptom**: Logs show `Audio callback status: input overflow`

**Solutions:**
1. Increase `queue.max_size` in config.yaml
2. Close other audio applications
3. Reduce system load (CPU/RAM usage)
4. Increase `chunk_ms` to 40ms (trades latency for stability)

## Performance Metrics

When `metrics.enabled: true`, the bot logs performance statistics:

```
📊 Metrics - Transcriptions: 42, Responses: 38, Skipped: 4, STT errors: 0, TTS errors: 0
⏱️  Latency - STT: 0.85s, TTS: 1.23s, E2E: 2.08s
```

**Metrics explained:**
- **Transcriptions**: Number of successful STT transcriptions
- **Responses**: Number of TTS responses generated
- **Skipped**: Responses blocked by cooldown
- **STT/TTS errors**: Error counts for debugging
- **STT latency**: Average time for speech-to-text
- **TTS latency**: Average time for text-to-speech generation
- **E2E latency**: Total time from speech detection to audio playback

**Target latencies:**
- STT: < 1.0s (depends on utterance length)
- TTS: < 2.0s (depends on response length + LLM speed)
- E2E: < 3.0s (total perceived delay)

## Advanced Configuration

### Multiple Bots

Run multiple instances with different configs:

```bash
# Bot 1: GLaDOS personality
python client.py --config glados_config.yaml

# Bot 2: HAL personality
python client.py --config hal_config.yaml
```

Each needs unique `input_device` or separate virtual audio cables.

### Custom VAD for Noisy Environments

For bars, conventions, or loud VRChat worlds:

```yaml
vad:
  silence_rms_threshold: 0.015  # Higher threshold
  silence_max_seconds: 0.5      # Shorter silence
  min_utterance_seconds: 0.5    # Longer minimum
  utterance_cooldown: 2.0       # More cooldown
```

### Low-Power Mode (Battery/Mobile)

Reduce CPU usage:

```yaml
audio:
  chunk_ms: 40  # Larger chunks = fewer callbacks

queue:
  max_size: 50  # Smaller queue

metrics:
  enabled: false  # Disable metrics
```

## Development

### Project Structure

```python
from app import (
    CrossPlatformRecorder,  # Audio capture
    Config, load_config,    # Configuration
    Metrics, metrics_logger,  # Performance tracking
    TTSClient,              # TTS API client
    VADState,               # Voice activity detection
    WebSocketHandler,       # STT communication
)
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest

# With coverage
pytest --cov=app
```

### Debugging

Enable DEBUG logging:

```yaml
logging:
  level: "DEBUG"
```

You'll see detailed logs:
```
DEBUG - RMS: 0.012 (voice detected)
DEBUG - Utterance started
DEBUG - Sending 320 bytes to STT
DEBUG - TTS request: {'text': 'hello there'}
```

## FAQ

**Q: Can I use my microphone instead of virtual audio?**  
A: Yes! Set `input_device: null` in config.yaml to use default microphone.

**Q: Does this work with Discord/TeamSpeak/Mumble?**  
A: Yes, configure those apps to output to your virtual audio device.

**Q: Can I run the client on a different machine than the server?**  
A: Yes, just set `pc_ip` to the server's IP address. Ensure ports 8000 and 8010 are accessible.

**Q: How much bandwidth does this use?**  
A: ~10-15 KB/s for audio streaming (PCM16 mono @ 16kHz) + minimal WebSocket overhead.

**Q: Can I use this for non-VRChat applications?**  
A: Yes! It works with any audio source routed to a virtual audio device.

**Q: Is there a GUI?**  
A: Not currently, but you can monitor via metrics logs or build one using the `app` package.

## Contributing

Contributions welcome! Key areas:

- [ ] GUI for easier configuration
- [ ] Voice cloning integration
- [ ] Multi-language support
- [ ] Cloud deployment guides
- [ ] Docker containerization
- [ ] Web-based metrics dashboard

## License

See main TTS server repository for license information.

## Support

- **Issues**: Open a GitHub issue
- **Docs**: See main TTS server README
- **Server setup**: Refer to `/tts_server/README.md`

## Version History

- **v2.0.0** - Cross-platform rewrite with sounddevice
  - ✅ Windows support
  - ✅ Simplified configuration
  - ✅ Improved error handling
  - ✅ Metrics tracking
  
- **v1.0.0** - Initial Linux-only PipeWire implementation
