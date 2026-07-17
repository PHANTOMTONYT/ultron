import { Room, RoomEvent, Track } from 'https://esm.sh/livekit-client@2.0.4';

const statusEl = document.getElementById('status');
const connectBtn = document.getElementById('connect-btn');
const muteBtn = document.getElementById('mute-btn');
const logEl = document.getElementById('log');
const transcriptEl = document.getElementById('transcript');

const textDecoder = new TextDecoder();

function addTranscriptLine(role, text) {
  const line = document.createElement('div');
  line.className = `line ${role === 'user' ? 'user' : 'assistant'}`;

  const who = document.createElement('span');
  who.className = 'who';
  who.textContent = role === 'user' ? 'You' : 'EDITH';

  const body = document.createElement('span');
  body.className = 'text';
  body.textContent = text;

  line.appendChild(who);
  line.appendChild(body);
  transcriptEl.appendChild(line);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

let room = null;
let micEnabled = true;

function log(msg) {
  const line = document.createElement('div');
  line.textContent = msg;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

function setStatus(text) {
  statusEl.textContent = text;
}

async function connect() {
  connectBtn.disabled = true;
  setStatus('Fetching token...');

  let data;
  try {
    const res = await fetch('/token');
    data = await res.json();
    if (data.error) throw new Error(data.error);
  } catch (e) {
    setStatus('Failed to get token: ' + e.message);
    connectBtn.disabled = false;
    return;
  }

  room = new Room();

  room.on(RoomEvent.Connected, () => {
    setStatus(`Connected to '${data.room}'`);
    log('Connected to room.');
  });

  room.on(RoomEvent.Disconnected, () => {
    setStatus('Disconnected');
    log('Disconnected from room.');
    connectBtn.disabled = false;
    connectBtn.textContent = 'Connect & Enable Mic';
    muteBtn.disabled = true;
  });

  room.on(RoomEvent.ParticipantConnected, (p) => {
    log(`Participant joined: ${p.identity}`);
  });

  room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
    if (track.kind === Track.Kind.Audio) {
      log(`Subscribed to audio from ${participant.identity}`);
      const el = track.attach();
      el.style.display = 'none';
      document.body.appendChild(el);
    }
  });

  room.on(RoomEvent.TrackUnsubscribed, (track) => {
    track.detach().forEach((el) => el.remove());
  });

  room.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
    if (topic !== 'transcript') return;
    try {
      const { role, text } = JSON.parse(textDecoder.decode(payload));
      if (text) addTranscriptLine(role, text);
    } catch (e) {
      console.error('Failed to parse transcript data:', e);
    }
  });

  try {
    await room.connect(data.url, data.token);
    await room.localParticipant.enableCameraAndMicrophone();
    micEnabled = true;
    muteBtn.disabled = false;
    muteBtn.textContent = 'Mute';
    connectBtn.textContent = 'Connected';
    log('Microphone published. Start talking to EDITH.');
  } catch (e) {
    setStatus('Connection failed: ' + e.message);
    log('Error: ' + e.message);
    connectBtn.disabled = false;
  }
}

connectBtn.addEventListener('click', connect);

muteBtn.addEventListener('click', async () => {
  if (!room) return;
  micEnabled = !micEnabled;
  await room.localParticipant.setMicrophoneEnabled(micEnabled);
  muteBtn.textContent = micEnabled ? 'Mute' : 'Unmute';
  muteBtn.classList.toggle('active', !micEnabled);
});
