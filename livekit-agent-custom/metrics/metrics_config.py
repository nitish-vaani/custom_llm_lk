import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class MetricsConfig:
    """Configuration for metrics collection"""
    
    # Enable/disable metrics
    enabled: bool = False
    
    # Storage settings
    storage_type: str = "memory"  # "memory", "redis", "file"
    
    # Redis settings (if using redis storage)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # File settings (if using file storage)
    file_path: str = "./metrics.jsonl"
    
    # Collection settings
    collect_llm_metrics: bool = True
    collect_tts_metrics: bool = True
    collect_asr_metrics: bool = True
    collect_eou_metrics: bool = True
    
    # Sampling settings (to reduce overhead)
    sample_rate: float = 1.0  # 1.0 = collect all, 0.1 = collect 10%
    
    @classmethod
    def from_env(cls) -> "MetricsConfig":
        """Create configuration from environment variables"""
        return cls(
            enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            storage_type=os.getenv("METRICS_STORAGE_TYPE", "memory"),
            redis_host=os.getenv("METRICS_REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("METRICS_REDIS_PORT", "6379")),
            redis_db=int(os.getenv("METRICS_REDIS_DB", "0")),
            redis_password=os.getenv("METRICS_REDIS_PASSWORD"),
            file_path=os.getenv("METRICS_FILE_PATH", "./metrics.jsonl"),
            collect_llm_metrics=os.getenv("METRICS_COLLECT_LLM", "true").lower() == "true",
            collect_tts_metrics=os.getenv("METRICS_COLLECT_TTS", "true").lower() == "true",
            collect_asr_metrics=os.getenv("METRICS_COLLECT_ASR", "true").lower() == "true",
            collect_eou_metrics=os.getenv("METRICS_COLLECT_EOU", "true").lower() == "true",
            sample_rate=float(os.getenv("METRICS_SAMPLE_RATE", "1.0")),
        )