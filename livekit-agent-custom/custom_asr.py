import os
from dotenv import load_dotenv
from livekit.plugins import deepgram

load_dotenv()

class CustomASR:
    def __init__(self, model="nova-2", language="en", smart_format=True):
        """
        Initialize Deepgram ASR with custom parameters
        
        Args:
            model (str): Deepgram model to use (nova-2, nova-3, enhanced, base)
            language (str): Language code (en, es, fr, etc.)
            smart_format (bool): Enable smart formatting
        """
        self.model = model
        self.language = language
        self.smart_format = smart_format
        
        # Verify API key is set
        if not os.getenv("DEEPGRAM_API_KEY"):
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
    
    def get_stt(self):
        """
        Returns configured Deepgram STT instance
        """
        return deepgram.STT(
            model=self.model,
            language=self.language,
            smart_format=self.smart_format
        )
    
    def update_config(self, **kwargs):
        """
        Update ASR configuration parameters
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self.get_stt()