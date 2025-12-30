# TTS Server Frontend

A simple, lightweight web interface for the TTS Server built with vanilla HTML, CSS, and JavaScript.

## Features

### 🎙️ Text-to-Speech Generation
- Input text and generate speech using the LLM + Piper TTS pipeline
- Select from available voice models
- Play generated audio directly in the browser
- Real-time loading indicators

### 📊 Performance Monitoring
- Live service health status (TTS, STT, Ollama)
- Prometheus metrics display:
  - Total TTS requests
  - Total STT transcriptions
  - LLM success rate
  - Average response time
- One-click metrics refresh

### ⚙️ Configuration View
- Display active server URLs
- Circuit breaker status
- Available voice models count

### 📚 API Documentation
- Quick reference for all API endpoints
- HTTP methods and descriptions

## Architecture

### Technology Stack
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3
- **Backend Integration**: REST API calls to FastAPI
- **Styling**: Custom CSS with dark theme and responsive design
- **No Build Process**: Direct file serving, no bundling required

### File Structure
```
frontend/
├── index.html          # Main HTML page
├── css/
│   └── style.css       # Styling (dark theme)
└── js/
    └── app.js          # Application logic
```

### Integration with FastAPI
The frontend is served as static files from the TTS server:

```python
# In tts/server.py
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")
```

## Usage

### Starting the Server
```bash
# Start TTS server (automatically serves frontend)
python -m uvicorn tts.server:app --host 0.0.0.0 --port 8000

# Or use the run script
python run_services.py
```

### Accessing the Frontend
Open your browser and navigate to:
```
http://localhost:8000
```

### Generating Speech
1. Select a voice model from the dropdown
2. Enter text in the text area (default: "Hello! How can I help you today?")
3. Click "🎵 Generate Speech"
4. Audio will be generated via LLM → Piper pipeline
5. Play the audio using the built-in player

### Monitoring Metrics
- Service health indicators update every 10 seconds automatically
- Click "🔄 Refresh Metrics" to manually update Prometheus metrics
- Metrics include:
  - Request counts (TTS, STT, LLM)
  - Success rates
  - Average processing times

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve frontend HTML |
| `/static/{path}` | GET | Serve CSS/JS files |
| `/health` | GET | Check service health |
| `/metrics` | GET | Get Prometheus metrics |
| `/voices` | GET | List available voice models |
| `/tts` | POST | Generate speech from text |

## Configuration

The frontend automatically detects server configuration:
- TTS server: `http://localhost:8000` (default)
- STT server: `http://localhost:8010` (default)

To change ports, update `config.yaml`:
```yaml
tts_host: "0.0.0.0"
tts_port: 8000
stt_host: "0.0.0.0"
stt_port: 8010
```

## Design Philosophy

### Minimal Complexity
- **No frameworks**: Pure vanilla JavaScript for minimal overhead
- **No build tools**: Direct file serving, no webpack/vite/etc.
- **No npm dependencies**: Zero package.json complexity
- **Single-page app**: All functionality in one HTML file

### Maintainability
- Clean separation of concerns (HTML/CSS/JS)
- Well-commented code
- Consistent naming conventions
- Responsive design for mobile/desktop

### Performance
- Lightweight: ~10KB total (HTML+CSS+JS)
- Fast loading: No external dependencies
- Auto-refresh only when needed (10s health checks)
- Efficient metrics parsing

## Browser Compatibility
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support (iOS 12+)
- Modern browsers with ES6 support required

## Development

### Adding New Features
1. **UI Components**: Add HTML in `index.html`
2. **Styling**: Update `css/style.css` (uses CSS variables for theming)
3. **Logic**: Extend `js/app.js` (uses module pattern)

### Debugging
Open browser DevTools console. The app exposes a debug API:
```javascript
// Access application state
console.log(window.TTSApp.state);

// Manually trigger functions
window.TTSApp.loadVoices();
window.TTSApp.loadMetrics();
window.TTSApp.generateSpeech();
```

### Customizing Theme
Edit CSS variables in `style.css`:
```css
:root {
    --bg-primary: #1a1a2e;
    --accent-blue: #00adb5;
    --accent-green: #00ff88;
    /* ... */
}
```

## Security Considerations
- **CORS**: Frontend runs on same origin as API (no CORS issues)
- **Input validation**: Text length limited by API (configurable in `config.yaml`)
- **No sensitive data**: No authentication/credentials stored
- **Rate limiting**: Handled by backend semaphore

## Future Enhancements (Optional)
- [ ] WebSocket integration for STT (real-time transcription)
- [ ] Voice recording from microphone
- [ ] Audio waveform visualization
- [ ] Dark/light theme toggle
- [ ] Export audio to file
- [ ] Speech history log
- [ ] Custom system prompts editor

## Troubleshooting

### Frontend not loading
```bash
# Check if frontend directory exists
ls frontend/

# Check if files are properly mounted
curl http://localhost:8000/static/js/app.js
```

### Metrics not displaying
- Ensure Prometheus metrics are enabled in both servers
- Check `/metrics` endpoint returns data
- Verify metrics parsing in browser console

### Audio not playing
- Check browser supports WAV playback
- Verify TTS server is running
- Check Ollama is available at `http://127.0.0.1:11434`
- Review browser console for errors

### Service status shows offline
- Confirm both STT and TTS servers are running
- Check ports match configuration (8000, 8010)
- Verify no firewall blocking localhost connections

## License
Part of the TTS Server project. See main project README for license information.
