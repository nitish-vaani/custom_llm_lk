import os
from dotenv import load_dotenv

load_dotenv()

class AgentConfig:
    """Configuration class for the LiveKit agent"""
    
    def __init__(self):
        # SIP Configuration
        self.outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
        self.client_name = os.getenv("CLIENT_NAME", "default_client")
        
        # LLM Configuration
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1000"))
        
        # ASR Configuration
        self.asr_model = os.getenv("ASR_MODEL", "nova-2")
        self.asr_language = os.getenv("ASR_LANGUAGE", "en")
        self.asr_smart_format = os.getenv("ASR_SMART_FORMAT", "true").lower() == "true"
        
        # TTS Configuration
        self.tts_voice = os.getenv("TTS_VOICE", "Rachel")
        self.tts_model = os.getenv("TTS_MODEL", "eleven_turbo_v2")
        self.tts_stability = float(os.getenv("TTS_STABILITY", "0.5"))
        self.tts_similarity_boost = float(os.getenv("TTS_SIMILARITY_BOOST", "0.8"))
        
        # VAD Configuration
        self.vad_min_silence_duration = float(os.getenv("VAD_MIN_SILENCE_DURATION", "0.1"))
        self.vad_min_speech_duration = float(os.getenv("VAD_MIN_SPEECH_DURATION", "0.1"))
        self.vad_max_buffered_speech = float(os.getenv("VAD_MAX_BUFFERED_SPEECH", "5.0"))
        
        # Validate required settings
        self.validate()
    
    def validate(self):
        """Validate required configuration"""
        if not self.outbound_trunk_id or not self.outbound_trunk_id.startswith("ST_"):
            raise ValueError("SIP_OUTBOUND_TRUNK_ID is not set properly")
        
        required_env_vars = [
            "OPENAI_API_KEY",
            "DEEPGRAM_API_KEY", 
            "ELEVENLABS_API_KEY"
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    def get_llm_config(self):
        """Get LLM configuration as dict"""
        return {
            "model": self.llm_model,
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens
        }
    
    def get_asr_config(self):
        """Get ASR configuration as dict"""
        return {
            "model": self.asr_model,
            "language": self.asr_language,
            "smart_format": self.asr_smart_format
        }
    
    def get_tts_config(self):
        """Get TTS configuration as dict"""
        return {
            "voice": self.tts_voice,
            "model": self.tts_model,
            "stability": self.tts_stability,
            "similarity_boost": self.tts_similarity_boost
        }
    
    def get_vad_config(self):
        """Get VAD configuration as dict"""
        return {
            "min_silence_duration": self.vad_min_silence_duration,
            "min_speech_duration": self.vad_min_speech_duration,
            "max_buffered_speech": self.vad_max_buffered_speech
        }