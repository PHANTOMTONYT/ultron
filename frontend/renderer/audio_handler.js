import EventEmitter from './event_emitter.js';

class AudioHandler extends EventEmitter {
  constructor() {
    super();
    this.audioQueue = [];
    this.isPlaying = false;
    this.currentAudio = null;
    
    // Web Audio API setup for volume analysis
    this.audioCtx = null;
    this.analyser = null;
    this.sourceNode = null;
    this.dataArray = null;
    
    this.recognition = null;
    this.isListening = false;
    
    this.initAudioContext();
    this.initSTT();
  }
  
  initAudioContext() {
    // Created eagerly; browsers keep it suspended until a user gesture,
    // which playNext() resumes on first playback.
    try {
      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 256;
      const bufferLength = this.analyser.frequencyBinCount;
      this.dataArray = new Uint8Array(bufferLength);
    } catch (e) {
      console.error('Web Audio API not supported:', e);
    }
  }
  
  initSTT() {
    if (!('webkitSpeechRecognition' in window)) {
      console.warn('Speech recognition not supported in this browser.');
      return;
    }
    
    this.recognition = new webkitSpeechRecognition();
    this.recognition.continuous = false; // We want single utterances
    this.recognition.interimResults = true; // Show text as user speaks
    this.recognition.lang = 'en-IN'; // Indian English default, matches config
    
    this.recognition.onstart = () => {
      console.log('STT: Listening...');
      this.isListening = true;
      this.emit('listening_started');
    };
    
    this.recognition.onerror = (event) => {
      console.error('STT Error:', event.error);
      this.isListening = false;
      this.emit('listening_stopped');
    };
    
    this.recognition.onend = () => {
      console.log('STT: Stopped listening.');
      this.isListening = false;
      this.emit('listening_stopped');
    };
    
    this.recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';
      
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }
      
      this.emit('transcript', {
        interim: interimTranscript,
        final: finalTranscript
      });
    };
  }
  
  startListening() {
    if (this.recognition && !this.isListening) {
      try {
        this.recognition.start();
      } catch (e) {
        console.error('Failed to start speech recognition:', e);
      }
    }
  }
  
  stopListening() {
    if (this.recognition && this.isListening) {
      this.recognition.stop();
    }
  }
  
  queueSpeech(base64Audio, text) {
    this.audioQueue.push({ base64Audio, text });
    if (!this.isPlaying) {
      this.playNext();
    }
  }
  
  playNext() {
    if (this.audioQueue.length === 0) {
      this.isPlaying = false;
      this.emit('speech_finished');
      return;
    }
    
    this.isPlaying = true;
    const { base64Audio, text } = this.audioQueue.shift();
    
    console.log(`STT/TTS: Speaking sentence: "${text}"`);
    
    // Create Audio Element with data URL
    const audioUrl = `data:audio/mp3;base64,${base64Audio}`;
    const audio = new Audio(audioUrl);
    this.currentAudio = audio;
    
    // Resume context if suspended (Chrome autoplay policy)
    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
    
    // Route audio through analyzer
    try {
      // Clean up previous source
      if (this.sourceNode) {
        this.sourceNode.disconnect();
      }
      
      this.sourceNode = this.audioCtx.createMediaElementSource(audio);
      this.sourceNode.connect(this.analyser);
      this.analyser.connect(this.audioCtx.destination);
    } catch (e) {
      // In case source node is already routed or other web audio bugs
      console.warn('Audio routing warning:', e);
    }
    
    audio.onplay = () => {
      this.emit('speech_started', { text });
    };
    
    audio.onended = () => {
      this.playNext();
    };
    
    audio.onerror = (e) => {
      console.error('Audio playback error:', e);
      this.playNext();
    };
    
    audio.play().catch(err => {
      console.error('Failed to play audio:', err);
      this.playNext();
    });
  }
  
  getAmplitude() {
    if (!this.analyser || !this.isPlaying) return 0.0;
    
    this.analyser.getByteFrequencyData(this.dataArray);
    
    // Compute root-mean-square or average of frequency data
    let sum = 0;
    for (let i = 0; i < this.dataArray.length; i++) {
      sum += this.dataArray[i];
    }
    const average = sum / this.dataArray.length;
    
    // Normalize to 0.0 - 1.0 range
    return average / 255.0;
  }
  
  clearQueue() {
    this.audioQueue = [];
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this.isPlaying = false;
    this.emit('speech_finished');
  }

  analyzeTrackElement(audioElement) {
    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
    try {
      if (this.sourceNode) {
        this.sourceNode.disconnect();
      }
      
      this.sourceNode = this.audioCtx.createMediaElementSource(audioElement);
      this.sourceNode.connect(this.analyser);
      this.analyser.connect(this.audioCtx.destination);
      
      this.isPlaying = true;
      
      // Bind event listeners to coordinate visual states
      audioElement.onplay = () => {
        this.isPlaying = true;
        this.emit('speech_started', { text: "LiveKit Audio" });
      };
      
      audioElement.onpause = () => {
        this.isPlaying = false;
        this.emit('speech_finished');
      };
      
      audioElement.onended = () => {
        this.isPlaying = false;
        this.emit('speech_finished');
      };
    } catch (e) {
      console.warn('Audio handler: Failed to route LiveKit audio track:', e);
    }
  }
}

export default AudioHandler;
