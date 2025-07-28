import json
import time
import random
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from .metrics_config import MetricsConfig

logger = logging.getLogger("metrics-collector")

@dataclass
class LLMMetric:
    """LLM performance metric"""
    timestamp: float
    call_id: str
    ttft: float  # Time to first token
    input_tokens: int
    output_tokens: int
    model: str
    total_time: float
    tokens_per_second: float

@dataclass
class TTSMetric:
    """TTS performance metric"""
    timestamp: float
    call_id: str
    ttfb: float  # Time to first byte
    audio_duration: float
    text_length: int
    model: str
    voice_id: str

@dataclass
class ASRMetric:
    """ASR performance metric"""
    timestamp: float
    call_id: str
    audio_duration: float
    processing_time: float
    text_length: int
    model: str
    language: str

@dataclass
class EOUMetric:
    """End of Utterance metric"""
    timestamp: float
    call_id: str
    eou_delay: float
    confidence: float

class MetricsStorage:
    """Base class for metrics storage"""
    
    async def store_metric(self, metric_type: str, metric: Dict[str, Any]):
        raise NotImplementedError
    
    async def get_metrics(self, call_id: str = None, metric_type: str = None) -> List[Dict[str, Any]]:
        raise NotImplementedError
    
    async def cleanup(self):
        pass

class MemoryStorage(MetricsStorage):
    """In-memory metrics storage"""
    
    def __init__(self):
        self.metrics: List[Dict[str, Any]] = []
    
    async def store_metric(self, metric_type: str, metric: Dict[str, Any]):
        metric["metric_type"] = metric_type
        self.metrics.append(metric)
    
    async def get_metrics(self, call_id: str = None, metric_type: str = None) -> List[Dict[str, Any]]:
        results = self.metrics
        
        if call_id:
            results = [m for m in results if m.get("call_id") == call_id]
        
        if metric_type:
            results = [m for m in results if m.get("metric_type") == metric_type]
        
        return results

class FileStorage(MetricsStorage):
    """File-based metrics storage (JSONL format)"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
    
    async def store_metric(self, metric_type: str, metric: Dict[str, Any]):
        metric["metric_type"] = metric_type
        
        # Append to file
        with open(self.file_path, "a") as f:
            f.write(json.dumps(metric) + "\n")
    
    async def get_metrics(self, call_id: str = None, metric_type: str = None) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r") as f:
                metrics = [json.loads(line.strip()) for line in f if line.strip()]
        except FileNotFoundError:
            return []
        
        if call_id:
            metrics = [m for m in metrics if m.get("call_id") == call_id]
        
        if metric_type:
            metrics = [m for m in metrics if m.get("metric_type") == metric_type]
        
        return metrics

class RedisStorage(MetricsStorage):
    """Redis-based metrics storage"""
    
    def __init__(self, config: MetricsConfig):
        self.config = config
        self.redis_client = None
    
    async def _get_redis(self):
        if self.redis_client is None:
            try:
                import redis.asyncio as aioredis
                self.redis_client = aioredis.Redis(
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    db=self.config.redis_db,
                    password=self.config.redis_password,
                    decode_responses=True
                )
            except ImportError:
                logger.error("Redis not available. Install redis with: pip install redis")
                raise
        return self.redis_client
    
    async def store_metric(self, metric_type: str, metric: Dict[str, Any]):
        redis = await self._get_redis()
        metric["metric_type"] = metric_type
        
        # Store in a list for the call_id
        call_id = metric.get("call_id", "unknown")
        key = f"metrics:{call_id}"
        
        await redis.lpush(key, json.dumps(metric))
        await redis.expire(key, 3600 * 24)  # Expire after 24 hours
    
    async def get_metrics(self, call_id: str = None, metric_type: str = None) -> List[Dict[str, Any]]:
        redis = await self._get_redis()
        
        if call_id:
            key = f"metrics:{call_id}"
            metric_strings = await redis.lrange(key, 0, -1)
            metrics = [json.loads(m) for m in metric_strings]
        else:
            # Get all keys matching pattern
            keys = await redis.keys("metrics:*")
            metrics = []
            for key in keys:
                metric_strings = await redis.lrange(key, 0, -1)
                metrics.extend([json.loads(m) for m in metric_strings])
        
        if metric_type:
            metrics = [m for m in metrics if m.get("metric_type") == metric_type]
        
        return metrics
    
    async def cleanup(self):
        if self.redis_client:
            await self.redis_client.close()

class MetricsCollector:
    """Main metrics collector class"""
    
    def __init__(self, config: MetricsConfig):
        self.config = config
        self.storage = self._create_storage()
        self.current_call_id: Optional[str] = None
    
    def _create_storage(self) -> MetricsStorage:
        """Create storage backend based on configuration"""
        if not self.config.enabled:
            return MemoryStorage()  # Use memory storage as no-op when disabled
        
        if self.config.storage_type == "redis":
            return RedisStorage(self.config)
        elif self.config.storage_type == "file":
            return FileStorage(self.config.file_path)
        else:
            return MemoryStorage()
    
    def _should_collect(self) -> bool:
        """Determine if we should collect this metric based on sampling rate"""
        if not self.config.enabled:
            return False
        return random.random() < self.config.sample_rate
    
    def set_call_id(self, call_id: str):
        """Set the current call ID for metrics"""
        self.current_call_id = call_id
    
    async def record_llm_metric(
        self,
        ttft: float,
        input_tokens: int,
        output_tokens: int,
        model: str,
        total_time: float
    ):
        """Record LLM performance metric"""
        if not self.config.collect_llm_metrics or not self._should_collect():
            return
        
        tokens_per_second = output_tokens / total_time if total_time > 0 else 0
        
        metric = LLMMetric(
            timestamp=time.time(),
            call_id=self.current_call_id or "unknown",
            ttft=ttft,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            total_time=total_time,
            tokens_per_second=tokens_per_second
        )
        
        await self.storage.store_metric("llm", asdict(metric))
        logger.debug(f"📊 LLM metric recorded: TTFT={ttft:.3f}s, tokens={input_tokens}/{output_tokens}")
    
    async def record_tts_metric(
        self,
        ttfb: float,
        audio_duration: float,
        text_length: int,
        model: str,
        voice_id: str
    ):
        """Record TTS performance metric"""
        if not self.config.collect_tts_metrics or not self._should_collect():
            return
        
        metric = TTSMetric(
            timestamp=time.time(),
            call_id=self.current_call_id or "unknown",
            ttfb=ttfb,
            audio_duration=audio_duration,
            text_length=text_length,
            model=model,
            voice_id=voice_id
        )
        
        await self.storage.store_metric("tts", asdict(metric))
        logger.debug(f"📊 TTS metric recorded: TTFB={ttfb:.3f}s, duration={audio_duration:.3f}s")
    
    async def record_asr_metric(
        self,
        audio_duration: float,
        processing_time: float,
        text_length: int,
        model: str,
        language: str
    ):
        """Record ASR performance metric"""
        if not self.config.collect_asr_metrics or not self._should_collect():
            return
        
        metric = ASRMetric(
            timestamp=time.time(),
            call_id=self.current_call_id or "unknown",
            audio_duration=audio_duration,
            processing_time=processing_time,
            text_length=text_length,
            model=model,
            language=language
        )
        
        await self.storage.store_metric("asr", asdict(metric))
        logger.debug(f"📊 ASR metric recorded: processing={processing_time:.3f}s, text_len={text_length}")
    
    async def record_eou_metric(self, eou_delay: float, confidence: float = 1.0):
        """Record End of Utterance metric"""
        if not self.config.collect_eou_metrics or not self._should_collect():
            return
        
        metric = EOUMetric(
            timestamp=time.time(),
            call_id=self.current_call_id or "unknown",
            eou_delay=eou_delay,
            confidence=confidence
        )
        
        await self.storage.store_metric("eou", asdict(metric))
        logger.debug(f"📊 EOU metric recorded: delay={eou_delay:.3f}s")
    
    async def get_call_metrics(self, call_id: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get metrics for a specific call or all calls"""
        call_id = call_id or self.current_call_id
        
        llm_metrics = await self.storage.get_metrics(call_id, "llm")
        tts_metrics = await self.storage.get_metrics(call_id, "tts")
        asr_metrics = await self.storage.get_metrics(call_id, "asr")
        eou_metrics = await self.storage.get_metrics(call_id, "eou")
        
        return {
            "llm": llm_metrics,
            "tts": tts_metrics,
            "asr": asr_metrics,
            "eou": eou_metrics
        }
    
    async def get_call_summary(self, call_id: str = None) -> Dict[str, Any]:
        """Get a summary of metrics for a call"""
        metrics = await self.get_call_metrics(call_id)
        
        summary = {
            "call_id": call_id or self.current_call_id,
            "timestamp": datetime.now().isoformat(),
            "counts": {
                "llm_requests": len(metrics["llm"]),
                "tts_requests": len(metrics["tts"]),
                "asr_requests": len(metrics["asr"]),
                "eou_events": len(metrics["eou"])
            }
        }
        
        # LLM summary
        if metrics["llm"]:
            llm_ttfts = [m["ttft"] for m in metrics["llm"]]
            summary["llm"] = {
                "avg_ttft": sum(llm_ttfts) / len(llm_ttfts),
                "max_ttft": max(llm_ttfts),
                "min_ttft": min(llm_ttfts),
                "total_input_tokens": sum(m["input_tokens"] for m in metrics["llm"]),
                "total_output_tokens": sum(m["output_tokens"] for m in metrics["llm"]),
            }
        
        # TTS summary
        if metrics["tts"]:
            tts_ttfbs = [m["ttfb"] for m in metrics["tts"]]
            summary["tts"] = {
                "avg_ttfb": sum(tts_ttfbs) / len(tts_ttfbs),
                "max_ttfb": max(tts_ttfbs),
                "min_ttfb": min(tts_ttfbs),
                "total_audio_duration": sum(m["audio_duration"] for m in metrics["tts"]),
            }
        
        # ASR summary
        if metrics["asr"]:
            asr_times = [m["processing_time"] for m in metrics["asr"]]
            summary["asr"] = {
                "avg_processing_time": sum(asr_times) / len(asr_times),
                "max_processing_time": max(asr_times),
                "min_processing_time": min(asr_times),
                "total_audio_processed": sum(m["audio_duration"] for m in metrics["asr"]),
            }
        
        # EOU summary
        if metrics["eou"]:
            eou_delays = [m["eou_delay"] for m in metrics["eou"]]
            summary["eou"] = {
                "avg_delay": sum(eou_delays) / len(eou_delays),
                "max_delay": max(eou_delays),
                "min_delay": min(eou_delays),
            }
        
        return summary
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.storage.cleanup()