import os
from dotenv import load_dotenv
from livekit.plugins import elevenlabs

load_dotenv()

class CustomTTS:
    def __init__(self, voice="Rachel", model="eleven_turbo_v2", stability=0.5, similarity_boost=0.8):
        """
        Initialize ElevenLabs TTS with custom parameters
        
        Args:
            voice (str): Voice ID or name
            model (str): ElevenLabs model to use
            stability (float): Voice stability (0.0-1.0)
            similarity_boost (float): Voice similarity boost (0.0-1.0)
        """
        self.voice = voice
        self.model = model
        self.stability = stability
        self.similarity_boost = similarity_boost
        
        # Verify API key is set
        if not os.getenv("ELEVENLABS_API_KEY"):
            raise ValueError("ELEVENLABS_API_KEY environment variable is required")
    
    def get_tts(self):
        """
        Returns configured ElevenLabs TTS instance
        """
        return elevenlabs.TTS(
            voice=self.voice,
            model=self.model,
            voice_settings=elevenlabs.VoiceSettings(
                stability=self.stability,
                similarity_boost=self.similarity_boost
            )
        )
    
    def update_config(self, **kwargs):
        """
        Update TTS configuration parameters
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self.get_tts()