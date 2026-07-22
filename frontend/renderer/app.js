import { Room, RoomEvent, Track } from 'https://esm.sh/livekit-client@2.0.4';
import CompanionVisualizer from './visualizer.js';
import AudioHandler from './audio_handler.js';
import WSClient from '../websocket/client.js';
import ASCIIBackground from './ascii_bg.js';


// 0. Initialize ASCII Background
const bgCanvas = document.getElementById('ascii-bg-canvas');
const asciiBg = new ASCIIBackground(bgCanvas);

// 1. Initialize Visualizer
const canvas = document.getElementById('visualizer-canvas');
const visualizer = new CompanionVisualizer(canvas);

// 2. Initialize Audio Handler (STT & Audio Player)
const audioHandler = new AudioHandler();

// 3. Initialize WebSocket Client (same host/port that served this page)
const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsClient = new WSClient(`${wsProtocol}//${location.host}/ws`);
wsClient.connect();

// Keep track of active state and update visualizer CSS filters dynamically
function updateVisualizerShadowColor(state) {
  let color = 'rgba(0, 242, 254, 0.4)'; // teal
  if (state === 'listening') color = 'rgba(225, 0, 255, 0.5)';
  if (state === 'thinking') color = 'rgba(255, 8, 68, 0.5)';
  if (state === 'speaking') color = 'rgba(0, 198, 255, 0.5)';
  if (state === 'happy' || state === 'celebrating') color = 'rgba(246, 211, 101, 0.5)';
  if (state === 'sleeping') color = 'rgba(51, 8, 103, 0.2)';
  
  canvas.style.filter = `drop-shadow(0 0 15px ${color})`;
}

// 4. UI Elements interaction
const settingsTrigger = document.getElementById('settings-trigger');
const settingsPanel = document.getElementById('settings-panel');
const closeSettings = document.getElementById('close-settings');
const stateButtons = document.querySelectorAll('.btn-state');
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat-btn');
const micToggleBtn = document.getElementById('mic-toggle-btn');
const statusDot = document.getElementById('status-dot');
const connectionText = document.getElementById('connection-text');
const micStatus = document.getElementById('mic-status');
const captionsOverlay = document.getElementById('captions-overlay');

// Open/Close settings panel
settingsTrigger.addEventListener('click', () => {
  settingsPanel.classList.add('open');
});

closeSettings.addEventListener('click', () => {
  settingsPanel.classList.remove('open');
});

// Manual state override buttons (for testing)
stateButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    stateButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    const state = btn.dataset.state;
    visualizer.setState(state);
    updateVisualizerShadowColor(state);
    
    // Send state change notification to backend
    wsClient.send('state_request', { state });
    
    // Handle mock speech triggers
    if (state === 'speaking') {
      visualizer.setSpeechAmplitude(0.3);
    } else {
      visualizer.setSpeechAmplitude(0.0);
    }
  });
});

// Text Chat input submission
function sendChatMessage() {
  const text = chatInput.value.trim();
  if (text) {
    wsClient.send('user_input', { text });
    chatInput.value = '';
    visualizer.setState('thinking');
    updateVisualizerShadowColor('thinking');
  }
}

sendChatBtn.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendChatMessage();
});

// 5. WebSocket Event handling
let lkRoom = null;
let livekitActive = false;

const btnModeWs = document.getElementById('btn-mode-ws');
const btnModeWebrtc = document.getElementById('btn-mode-webrtc');

// Push-to-toggle mic button (explicit user gesture, required for mic permission
// prompts to behave predictably in a real browser tab). Only drives the local
// Web Speech STT path - LiveKit WebRTC mode manages its own mic via the room.
micToggleBtn.addEventListener('click', () => {
  if (livekitActive) return; // Mic is owned by the LiveKit room in this mode
  if (audioHandler.isListening) {
    audioHandler.stopListening();
  } else {
    audioHandler.startListening();
  }
});

wsClient.on('connected', () => {
  statusDot.className = 'status-dot connected';
  connectionText.innerText = 'Connected';
  
  // Check if WebRTC connection is set as active mode
  if (btnModeWebrtc.classList.contains('active')) {
    wsClient.send('request_livekit_token');
  } else {
    // Default to Standard local STT loop - user starts listening via the mic button
    micStatus.innerText = 'Local STT (click mic to talk)';
    micStatus.style.color = '#00f2fe';
  }
});

wsClient.on('disconnected', () => {
  statusDot.className = 'status-dot';
  connectionText.innerText = 'Disconnected';
  livekitActive = false;
});

// Mode Toggle Event Listeners
btnModeWs.addEventListener('click', async () => {
  btnModeWs.classList.add('active');
  btnModeWebrtc.classList.remove('active');
  
  livekitActive = false;
  if (lkRoom) {
    try {
      await lkRoom.disconnect();
    } catch(e) {}
    lkRoom = null;
  }
  
  // Clear any existing WebRTC track playback volume
  audioHandler.clearQueue();
  
  // Notify backend to drop WebRTC and fallback to WS
  wsClient.send('toggle_voice_mode', { mode: 'ws' });
  
  micStatus.innerText = 'Local STT';
  micStatus.style.color = '#00f2fe';
  audioHandler.startListening();
  console.log('Voice mode: Switched to WebSocket fallback.');
});

btnModeWebrtc.addEventListener('click', () => {
  btnModeWebrtc.classList.add('active');
  btnModeWs.classList.remove('active');
  
  // Stop local transcription engine to handoff to LiveKit
  audioHandler.stopListening();
  
  wsClient.send('toggle_voice_mode', { mode: 'webrtc' });
  wsClient.send('request_livekit_token');
  
  micStatus.innerText = 'Connecting...';
  micStatus.style.color = 'orange';
  console.log('Voice mode: Switched to WebRTC.');
});


wsClient.on('livekit_token', async (msg) => {
  console.log('LiveKit: Connecting to room...');
  try {
    if (lkRoom) {
      await lkRoom.disconnect();
    }
    
    lkRoom = new Room();
    
    // Remote audio track subscriber callback
    lkRoom.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
      if (track.kind === Track.Kind.Audio) {
        console.log('LiveKit: Subscribed to audio track from:', participant.identity);
        const audioElement = track.attach();
        audioElement.style.display = 'none';
        document.body.appendChild(audioElement);
        
        // Analyze audio element volume in real-time
        audioHandler.analyzeTrackElement(audioElement);
      }
    });
    
    lkRoom.on(RoomEvent.TrackUnsubscribed, (track) => {
      track.detach();
    });
    
    await lkRoom.connect(msg.url, msg.token);
    console.log('LiveKit: Connected!');
    
    // Enable microphone and publish track
    await lkRoom.localParticipant.enableCameraAndMicrophone();
    console.log('LiveKit: Microphone published.');
    
    livekitActive = true;
    micStatus.innerText = 'VAD Active';
    micStatus.style.color = '#4cd964';
    
    // Stop any active Web Speech listener since LiveKit is active
    audioHandler.stopListening();
    
  } catch (e) {
    console.error('LiveKit: Connection failed, falling back to Web Speech STT:', e);
    livekitActive = false;
    micStatus.innerText = 'Local STT';
    micStatus.style.color = '#00f2fe';
    audioHandler.startListening();
  }
});

wsClient.on('livekit_unsupported', () => {
  console.log('LiveKit: Unsupported on backend. Falling back to local Web Speech STT.');
  livekitActive = false;
  micStatus.innerText = 'Local STT';
  micStatus.style.color = '#00f2fe';
  audioHandler.startListening();
});

wsClient.on('captions_overlay', (msg) => {
  if (msg.active && msg.text) {
    captionsOverlay.innerText = msg.text;
    captionsOverlay.classList.add('active');
  } else {
    captionsOverlay.classList.remove('active');
  }
});

wsClient.on('state_changed', (msg) => {
  console.log('WS: State Changed to', msg.state);
  visualizer.setState(msg.state);
  updateVisualizerShadowColor(msg.state);
  
  // Highlight manual state buttons if open
  stateButtons.forEach(btn => {
    if (btn.dataset.state === msg.state) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Start/Stop local Web Speech API listening ONLY if LiveKit is disabled
  if (!livekitActive) {
    if (msg.state === 'listening') {
      audioHandler.startListening();
    } else {
      audioHandler.stopListening();
    }
  }
});

wsClient.on('emotion_changed', (msg) => {
  console.log('WS: Emotion Changed to', msg.emotion);
  visualizer.setState(msg.emotion);
  updateVisualizerShadowColor(msg.emotion);
  if (msg.intensity !== undefined) {
    visualizer.emotionIntensity = msg.intensity;
  }
});

wsClient.on('audio_chunk', (msg) => {
  // Push raw base64 audio to direct queue (Fallback only)
  audioHandler.queueSpeech(msg.audio, msg.text);
});

wsClient.on('clear_audio', () => {
  audioHandler.clearQueue();
});


// 6. Voice and Speech events
audioHandler.on('listening_started', () => {
  micStatus.innerText = 'Listening';
  micStatus.style.color = '#e100ff';
  micToggleBtn.classList.add('listening');
  wsClient.send('listening_started');
});

audioHandler.on('listening_stopped', () => {
  micStatus.innerText = 'Idle';
  micStatus.style.color = 'rgba(255, 255, 255, 0.8)';
  micToggleBtn.classList.remove('listening');
  wsClient.send('listening_stopped');
});

audioHandler.on('transcript', (data) => {
  // Show transcript subtitles
  if (data.interim || data.final) {
    captionsOverlay.innerText = data.final || data.interim;
    captionsOverlay.classList.add('active');
  } else {
    captionsOverlay.classList.remove('active');
  }
  
  if (data.final) {
    // Send final transcript to backend
    wsClient.send('user_input', { text: data.final });
    visualizer.setState('thinking');
    updateVisualizerShadowColor('thinking');
    
    // Auto-hide captions after 3 seconds
    setTimeout(() => {
      if (captionsOverlay.innerText === data.final) {
        captionsOverlay.classList.remove('active');
      }
    }, 3000);
  }
});

audioHandler.on('speech_started', (data) => {
  visualizer.setState('speaking');
  updateVisualizerShadowColor('speaking');
  wsClient.send('speech_started');
});

audioHandler.on('speech_finished', () => {
  visualizer.setState('idle');
  updateVisualizerShadowColor('idle');
  wsClient.send('speech_finished');
});

// 7. Main frame synchronization loop for voice amplitude
function frameUpdate() {
  if (audioHandler.isPlaying && visualizer.currentState === 'speaking') {
    const amp = audioHandler.getAmplitude();
    visualizer.setSpeechAmplitude(amp);
  }
  requestAnimationFrame(frameUpdate);
}
frameUpdate();

// Handle window resizing
window.addEventListener('resize', () => {
  visualizer.resize(window.innerWidth, window.innerHeight);
  asciiBg.resize(window.innerWidth, window.innerHeight);
});
