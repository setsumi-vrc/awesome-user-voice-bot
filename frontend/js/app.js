// TTS Server Frontend Application
const API_BASE_URL = window.location.origin;

// State management
const state = {
    voices: [],
    models: [],
    personalities: [],
    metrics: {},
    config: {},
    chatLog: [],
    currentPersonality: '',
    editingPersonality: null
};

// Initialize application
document.addEventListener('DOMContentLoaded', async () => {
    await initializeApp();
    setupEventListeners();
    startAutoRefresh();
    loadChatLog();
});

// Initialize application data
async function initializeApp() {
    await Promise.all([
        checkServiceHealth(),
        loadVoices(),
        loadModels(),
        loadPersonalities(),
        loadMetrics(),
        loadConfig()
    ]);
}

// Setup event listeners
function setupEventListeners() {
    document.getElementById('generate-btn').addEventListener('click', generateSpeech);
    document.getElementById('refresh-metrics-btn').addEventListener('click', loadMetrics);
    document.getElementById('clear-log-btn').addEventListener('click', clearChatLog);
    document.getElementById('save-config-btn').addEventListener('click', saveServerConfig);

    // Personality controls
    document.getElementById('edit-personality-btn').addEventListener('click', editPersonality);
    document.getElementById('new-personality-btn').addEventListener('click', newPersonality);
    document.getElementById('close-modal').addEventListener('click', closeModal);
    document.getElementById('cancel-personality-btn').addEventListener('click', closeModal);
    document.getElementById('save-personality-btn').addEventListener('click', savePersonality);

    // Click outside modal to close
    document.getElementById('personality-modal').addEventListener('click', (e) => {
        if (e.target.id === 'personality-modal') {
            closeModal();
        }
    });

    // Allow Enter key to generate (Ctrl+Enter in textarea)
    document.getElementById('text-input').addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            generateSpeech();
        }
    });

    // Setup slider live updates
    setupSlider('speaker-id', 'speaker-id-val', (v) => Math.round(v));
    setupSlider('length-scale', 'length-scale-val', (v) => v.toFixed(2) + 'x');
    setupSlider('noise-scale', 'noise-scale-val', (v) => v.toFixed(2));
    setupSlider('noise-w', 'noise-w-val', (v) => v.toFixed(2));

    // Reset advanced settings
    const resetBtn = document.getElementById('reset-advanced-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetAdvancedSettings);
    }
}

// Setup slider with live value update
function setupSlider(sliderId, valueId, formatter) {
    const slider = document.getElementById(sliderId);
    const valueDisplay = document.getElementById(valueId);
    slider.addEventListener('input', (e) => {
        valueDisplay.textContent = formatter(parseFloat(e.target.value));
    });
}

// Reset advanced settings to defaults
function resetAdvancedSettings() {
    document.getElementById('speaker-id').value = 12;
    document.getElementById('speaker-id-val').textContent = '12';

    document.getElementById('length-scale').value = 1.0;
    document.getElementById('length-scale-val').textContent = '1.00x';

    document.getElementById('noise-scale').value = 0.667;
    document.getElementById('noise-scale-val').textContent = '0.67';

    document.getElementById('noise-w').value = 0.8;
    document.getElementById('noise-w-val').textContent = '0.80';

    showSuccess('⚙️ Advanced settings reset to defaults');
}

// Check service health status
async function checkServiceHealth() {
    const statusIndicators = {
        'tts-status': { url: `${API_BASE_URL}/health`, name: 'TTS' },
        'stt-status': { url: `http://localhost:8010/health`, name: 'STT' }
    };

    for (const [id, service] of Object.entries(statusIndicators)) {
        const indicator = document.getElementById(id);
        try {
            const response = await fetch(service.url, {
                method: 'GET',
                mode: 'cors',
                cache: 'no-cache'
            });
            if (response.ok) {
                indicator.textContent = '✅';
                indicator.title = `${service.name} is healthy`;
            } else {
                indicator.textContent = '⚠️';
                indicator.title = `${service.name} returned ${response.status}`;
            }
        } catch (error) {
            indicator.textContent = '🔴';
            indicator.title = `${service.name} is unreachable: ${error.message}`;
        }
    }

    for (const [id, config] of Object.entries(statusIndicators)) {
        try {
            const response = await fetch(config.url, { timeout: 2000 });
            const indicator = document.getElementById(id);

            if (response.ok) {
                indicator.textContent = '🟢';
                indicator.title = `${config.name} is healthy`;
            } else {
                indicator.textContent = '🔴';
                indicator.title = `${config.name} returned error ${response.status}`;
            }
        } catch (error) {
            document.getElementById(id).textContent = '🔴';
            document.getElementById(id).title = `${config.name} is unreachable`;
        }
    }

    // Check Ollama status via TTS health
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        const ollamaIndicator = document.getElementById('ollama-status');

        if (data.ollama) {
            ollamaIndicator.textContent = '🟢';
            ollamaIndicator.title = 'Ollama is available';
        } else {
            ollamaIndicator.textContent = '🟡';
            ollamaIndicator.title = 'Ollama may be unavailable';
        }
    } catch (error) {
        document.getElementById('ollama-status').textContent = '🔴';
    }
}

// Load available voices
async function loadVoices() {
    try {
        const response = await fetch(`${API_BASE_URL}/voices`);
        const data = await response.json();
        state.voices = data.voices || [];

        const voiceSelect = document.getElementById('voice-select');
        voiceSelect.innerHTML = state.voices.length > 0
            ? state.voices.map(voice => `<option value="${voice}">${voice}</option>`).join('')
            : '<option value="">No voices available</option>';

        document.getElementById('config-voices-count').textContent = state.voices.length;
    } catch (error) {
        console.error('Failed to load voices:', error);
        document.getElementById('voice-select').innerHTML = '<option value="">Error loading voices</option>';
    }
}

// Load available AI models
async function loadModels() {
    try {
        const response = await fetch(`${API_BASE_URL}/models`);
        const data = await response.json();
        state.models = data.models || [];

        const modelSelect = document.getElementById('model-select');
        if (state.models.length > 0) {
            modelSelect.innerHTML = state.models.map(m => {
                const isDefault = m === data.current;
                return `<option value="${m}" ${isDefault ? 'selected' : ''}>${m}${isDefault ? ' (default)' : ''}</option>`;
            }).join('');
        } else {
            modelSelect.innerHTML = '<option value="">No models available</option>';
        }
    } catch (error) {
        console.error('Failed to load models:', error);
        document.getElementById('model-select').innerHTML = '<option value="">Error loading models</option>';
    }
}

// Load available personalities
async function loadPersonalities() {
    try {
        const response = await fetch(`${API_BASE_URL}/personalities`);
        const data = await response.json();
        state.personalities = data.personalities || [];

        const personalitySelect = document.getElementById('personality-select');
        personalitySelect.innerHTML = state.personalities.length > 0
            ? state.personalities.map(p => `<option value="${p}">${p}</option>`).join('')
            : '<option value="">No personalities available</option>';

        // Select first personality by default
        if (state.personalities.length > 0) {
            state.currentPersonality = state.personalities[0];
        }
    } catch (error) {
        console.error('Failed to load personalities:', error);
        document.getElementById('personality-select').innerHTML = '<option value="">Error loading personalities</option>';
    }
}

// Generate speech from text
async function generateSpeech() {
    const textInput = document.getElementById('text-input');
    const voiceSelect = document.getElementById('voice-select');
    const modelSelect = document.getElementById('model-select');
    const personalitySelect = document.getElementById('personality-select');
    const generateBtn = document.getElementById('generate-btn');
    const loadingDiv = document.getElementById('loading');
    const audioPlayer = document.getElementById('audio-player');
    const audioElement = document.getElementById('audio');
    const errorMessage = document.getElementById('error-message');

    const text = textInput.value.trim();
    const voice = voiceSelect.value;
    const model = modelSelect.value;
    const personality = personalitySelect.value;

    if (!text) {
        showError('Please enter some text to convert to speech');
        return;
    }

    // Show loading state
    generateBtn.disabled = true;
    loadingDiv.style.display = 'flex';
    audioPlayer.style.display = 'none';
    errorMessage.style.display = 'none';

    try {
        // Build request with voice parameters
        const requestBody = { text: text };

        // Add personality if selected
        if (personality && personality !== '') {
            requestBody.personality = personality;
        }

        // Add model if selected
        if (model && model !== '') {
            requestBody.model = model;
        }

        // Add voice if selected
        if (voice && voice !== '') {
            requestBody.voice = voice;
        }

        // Add advanced parameters
        const speakerId = parseInt(document.getElementById('speaker-id').value);
        const lengthScale = parseFloat(document.getElementById('length-scale').value);
        const noiseScale = parseFloat(document.getElementById('noise-scale').value);
        const noiseW = parseFloat(document.getElementById('noise-w').value);

        if (speakerId !== 12) requestBody.speaker_id = speakerId;
        if (lengthScale !== 1.0) requestBody.length_scale = lengthScale;
        if (noiseScale !== 0.667) requestBody.noise_scale = noiseScale;
        if (noiseW !== 0.8) requestBody.noise_w = noiseW;

        const startTime = Date.now();

        const response = await fetch(`${API_BASE_URL}/tts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        const duration = ((Date.now() - startTime) / 1000).toFixed(2);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        // Get bot response text from header (if provided)
        const botResponse = response.headers.get('X-Bot-Response') || 'Generated response';

        // Get audio blob and create URL
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);

        // Display audio player
        audioElement.src = audioUrl;
        audioPlayer.style.display = 'block';
        audioElement.play();

        // Add to chat log with actual bot response
        addToChatLog('user', text, personality || 'default', null, model || 'default');
        addToChatLog('bot', botResponse, voice || 'default', duration, model || 'default');
    } catch (error) {
        showError(`Failed to generate speech: ${error.message}`);
    } finally {
        generateBtn.disabled = false;
        loadingDiv.style.display = 'none';
    }
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

// Load and parse Prometheus metrics
async function loadMetrics() {
    try {
        const response = await fetch(`${API_BASE_URL}/metrics`);
        const metricsText = await response.text();

        // Parse metrics
        const metrics = parsePrometheusMetrics(metricsText);
        state.metrics = metrics;

        // Update UI
        updateMetricsDisplay(metrics);
    } catch (error) {
        console.error('Failed to load metrics:', error);
    }
}

// Parse Prometheus metrics format
function parsePrometheusMetrics(text) {
    const metrics = {};
    const lines = text.split('\n');

    for (const line of lines) {
        if (line.startsWith('#') || !line.trim()) continue;

        const match = line.match(/^([a-z_]+)(?:{([^}]+)})?\s+([\d.]+)/);
        if (match) {
            const [, name, labels, value] = match;
            const key = labels ? `${name}{${labels}}` : name;
            metrics[key] = parseFloat(value);
        }
    }

    return metrics;
}

// Update metrics display
function updateMetricsDisplay(metrics) {
    // TTS requests
    const ttsTotal = Object.keys(metrics)
        .filter(k => k.startsWith('tts_requests_total'))
        .reduce((sum, k) => sum + metrics[k], 0);
    document.getElementById('metric-tts-requests').textContent = ttsTotal || 0;

    // STT transcriptions
    const sttTotal = metrics['stt_transcription_requests_total'] || 0;
    document.getElementById('metric-stt-requests').textContent = sttTotal;

    // LLM success rate
    const llmSuccess = metrics['llm_requests_total{status="success"}'] || 0;
    const llmTotal = Object.keys(metrics)
        .filter(k => k.startsWith('llm_requests_total'))
        .reduce((sum, k) => sum + metrics[k], 0);
    const successRate = llmTotal > 0 ? ((llmSuccess / llmTotal) * 100).toFixed(1) : 0;
    document.getElementById('metric-llm-success').textContent = `${successRate}%`;

    // Average response time (from histogram)
    const durationSum = metrics['tts_request_duration_seconds_sum'] || 0;
    const durationCount = metrics['tts_request_duration_seconds_count'] || 0;
    const avgTime = durationCount > 0 ? (durationSum / durationCount).toFixed(2) : 0;
    document.getElementById('metric-avg-time').textContent = `${avgTime}s`;
}

// Load configuration info
async function loadConfig() {
    const ttsPort = window.location.port || 8000;
    const sttPort = 8010;

    document.getElementById('config-tts-url').textContent = `http://localhost:${ttsPort}`;
    document.getElementById('config-stt-url').textContent = `http://localhost:${sttPort}`;

    // Try to detect circuit breaker status from health endpoint
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            document.getElementById('config-circuit-breaker').textContent = '✅ Enabled';
            document.getElementById('config-circuit-breaker').style.color = 'var(--accent-green)';
        }
    } catch (error) {
        document.getElementById('config-circuit-breaker').textContent = '❌ Unknown';
    }
}

// Auto-refresh health status every 10 seconds
function startAutoRefresh() {
    setInterval(() => {
        checkServiceHealth();
    }, 10000);

    // Auto-refresh conversation log every 5 seconds
    setInterval(() => {
        loadServerConversations();
    }, 5000);
}

// Utility: fetch with timeout
async function fetchWithTimeout(url, options = {}, timeout = 5000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        throw error;
    }
}

// Chat log functions
function loadChatLog() {
    // Load from server instead of localStorage
    loadServerConversations();
}

async function loadServerConversations() {
    try {
        const response = await fetch(`${API_BASE_URL}/conversations?limit=100`);
        const data = await response.json();

        // Convert server format to frontend format
        state.chatLog = [];
        for (const conv of data.conversations) {
            // Add user message
            state.chatLog.push({
                role: 'user',
                text: conv.user_text,
                voice: conv.voice || 'default',
                model: conv.model || 'default',
                timestamp: conv.timestamp,
                duration: null
            });

            // Add bot response with duration
            state.chatLog.push({
                role: 'bot',
                text: conv.bot_response,
                voice: conv.voice || 'default',
                model: conv.model || 'default',
                timestamp: conv.timestamp,
                duration: conv.duration || null
            });
        }

        renderChatLog();
    } catch (error) {
        console.error('Failed to load server conversations:', error);
    }
}

function saveChatLog() {
    // No longer needed - server handles persistence
}

function addToChatLog(role, text, voice, duration = null, model = null) {
    const message = {
        role: role,
        text: text,
        voice: voice,
        model: model,
        timestamp: new Date().toISOString(),
        duration: duration
    };

    state.chatLog.push(message);
    renderChatLog();
}

async function clearChatLog() {
    if (confirm('Clear all conversation history?')) {
        try {
            await fetch(`${API_BASE_URL}/conversations`, { method: 'DELETE' });
            state.chatLog = [];
            renderChatLog();
        } catch (error) {
            console.error('Failed to clear conversations:', error);
        }
    }
}

function renderChatLog() {
    const chatLogContainer = document.getElementById('chat-log');
    const messageCount = document.getElementById('message-count');

    if (state.chatLog.length === 0) {
        chatLogContainer.innerHTML = '<div class="chat-empty">No conversations yet. Generate speech to see the log.</div>';
        messageCount.textContent = '0';
        return;
    }

    messageCount.textContent = state.chatLog.length;

    chatLogContainer.innerHTML = state.chatLog.map((msg, idx) => {
        const time = new Date(msg.timestamp).toLocaleTimeString();
        const roleLabel = msg.role === 'user' ? '👤 User Input' : '🤖 Bot Response';
        const voiceInfo = msg.voice !== 'default' ? ` | Voice: ${msg.voice}` : '';
        const modelInfo = msg.model && msg.model !== 'default' ? ` | Model: ${msg.model}` : '';
        const durationInfo = msg.duration ? ` | ${msg.duration}s` : '';

        return `
            <div class="chat-message ${msg.role}">
                <div class="chat-message-header">
                    <span class="chat-message-role">${roleLabel}</span>
                    <span class="chat-message-time">${time}</span>
                </div>
                <div class="chat-message-text">${escapeHtml(msg.text)}</div>
                ${voiceInfo || modelInfo || durationInfo ? `<div class="chat-message-voice">${modelInfo}${voiceInfo}${durationInfo}</div>` : ''}
            </div>
        `;
    }).reverse().join('');

    // Auto-scroll to bottom (latest message)
    chatLogContainer.scrollTop = 0;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Personality editor functions
function editPersonality() {
    const personalitySelect = document.getElementById('personality-select');
    const personality = personalitySelect.value;

    if (!personality) {
        showError('Please select a personality to edit');
        return;
    }

    state.editingPersonality = personality;
    openModal('Edit Personality', personality);
}

function newPersonality() {
    state.editingPersonality = null;
    openModal('Create New Personality', '');
}

async function openModal(title, personalityName) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('personality-name').value = personalityName;

    // Load personality content if editing
    if (personalityName) {
        try {
            const response = await fetch(`${API_BASE_URL}/personalities/${personalityName}`);
            const data = await response.json();
            document.getElementById('personality-content').value = data.content || '';
        } catch (error) {
            console.error('Failed to load personality content:', error);
            showError('Failed to load personality content');
        }
    } else {
        document.getElementById('personality-content').value = '';
    }

    document.getElementById('personality-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('personality-modal').style.display = 'none';
    state.editingPersonality = null;
}

async function savePersonality() {
    const name = document.getElementById('personality-name').value.trim();
    const content = document.getElementById('personality-content').value.trim();

    if (!name) {
        showError('Please enter a personality name');
        return;
    }

    if (!content) {
        showError('Please enter a system prompt');
        return;
    }

    // Validate name (alphanumeric, hyphens, underscores only)
    if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
        showError('Personality name can only contain letters, numbers, hyphens, and underscores');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/personalities/${name}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content: content })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        // Reload personalities and select the new one
        await loadPersonalities();
        document.getElementById('personality-select').value = name;
        state.currentPersonality = name;

        closeModal();
        showSuccess(`Personality "${name}" saved successfully!`);

    } catch (error) {
        showError(`Failed to save personality: ${error.message}`);
    }
}

function showSuccess(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    errorDiv.style.background = 'rgba(0, 255, 136, 0.1)';
    errorDiv.style.borderLeft = '4px solid var(--accent-green)';
    errorDiv.style.color = 'var(--accent-green)';
    setTimeout(() => {
        errorDiv.style.display = 'none';
        errorDiv.style.background = '';
        errorDiv.style.borderLeft = '';
        errorDiv.style.color = '';
    }, 3000);
}

// Save server configuration
async function saveServerConfig() {
    const btn = document.getElementById('save-config-btn');
    const originalText = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '⏳ Applying...';

        const personality = document.getElementById('personality-select').value;
        const model = document.getElementById('model-select').value;
        const voice = document.getElementById('voice-select').value;
        const speakerId = parseInt(document.getElementById('speaker-id').value);
        const lengthScale = parseFloat(document.getElementById('length-scale').value);
        const noiseScale = parseFloat(document.getElementById('noise-scale').value);
        const noiseW = parseFloat(document.getElementById('noise-w').value);

        const config = {
            personality: personality || null,
            model: model || null,
            voice: voice || null,
            speaker_id: speakerId,
            length_scale: lengthScale,
            noise_scale: noiseScale,
            noise_w: noiseW
        };

        const response = await fetch(`${API_BASE_URL}/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });

        if (!response.ok) {
            throw new Error('Failed to save configuration');
        }

        btn.innerHTML = '✅ Applied!';
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 2000);

        showSuccess('✅ Configuration applied successfully! All clients will use these settings.');
    } catch (error) {
        btn.innerHTML = originalText;
        btn.disabled = false;
        showError(`Failed to save configuration: ${error.message}`);
    }
}

// Export for debugging
window.TTSApp = {
    state,
    loadVoices,
    loadModels,
    loadPersonalities,
    loadMetrics,
    generateSpeech,
    saveServerConfig,
    clearChatLog
};
