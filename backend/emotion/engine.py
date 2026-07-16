class EmotionEngine:
    def __init__(self):
        self.current_state = "idle"
        self.current_emotion = "idle"
        self.intensity = 0.5
        
        # Track active timers or temporary state overrides
        self.state_history = []

    def set_state(self, state: str, intensity: float = 0.5) -> dict:
        """
        Force sets the visual state and emotion.
        Returns a payload dictionary to broadcast to the clients.
        """
        self.current_state = state
        self.current_emotion = state
        self.intensity = intensity
        return {
            "type": "state_changed",
            "state": state,
            "intensity": intensity
        }

    def set_emotion(self, emotion: str, intensity: float = 0.5) -> dict:
        """
        Sets a specific emotion (happy, excited, confused, etc.).
        Returns the event payload.
        """
        self.current_emotion = emotion
        self.intensity = intensity
        return {
            "type": "emotion_changed",
            "emotion": emotion,
            "intensity": intensity
        }

    def process_event(self, event_type: str, payload: dict = None) -> dict:
        """
        State machine transitions based on incoming system events.
        """
        if payload is None:
            payload = {}
            
        print(f"Emotion Engine: Processing event '{event_type}'")
        
        if event_type == "listening_started":
            return self.set_state("listening", 0.7)
            
        elif event_type == "listening_stopped":
            # Only go back to idle if we were actually listening
            if self.current_state == "listening":
                return self.set_state("idle", 0.5)
                
        elif event_type == "thinking_started":
            return self.set_state("thinking", 0.8)
            
        elif event_type == "speech_started":
            return self.set_state("speaking", 0.6)
            
        elif event_type == "speech_finished":
            # Go back to idle when speaking is completed
            if self.current_state == "speaking":
                return self.set_state("idle", 0.5)
                
        elif event_type == "browser_changed":
            url = payload.get("url", "")
            # Check reactions based on URL
            from backend.browser.tracker import BrowserTracker
            tracker = BrowserTracker()
            reaction = tracker.determine_reaction(url)
            if reaction:
                print(f"Emotion Engine: URL Reaction triggered -> {reaction['emotion']}")
                return self.set_emotion(reaction["emotion"], reaction["intensity"])
                
        elif event_type == "wake_word_detected":
            return self.set_emotion("excited", 0.8)
            
        elif event_type == "sleep_mode":
            return self.set_state("sleeping", 0.3)
            
        return {}
