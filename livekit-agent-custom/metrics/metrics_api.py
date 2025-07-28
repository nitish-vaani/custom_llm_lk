import json
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .metrics_config import MetricsConfig
from .metrics_collector import MetricsCollector

app = FastAPI(title="LiveKit Agent Metrics API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global metrics collector
metrics_collector: Optional[MetricsCollector] = None

@app.on_event("startup")
async def startup_event():
    """Initialize metrics collector on startup"""
    global metrics_collector
    try:
        config = MetricsConfig.from_env()
        if config.enabled:
            metrics_collector = MetricsCollector(config)
            print(f"📊 Metrics API started with {config.storage_type} storage")
        else:
            print("📊 Metrics collection is disabled")
    except Exception as e:
        print(f"❌ Failed to initialize metrics collector: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global metrics_collector
    if metrics_collector:
        await metrics_collector.cleanup()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "metrics_enabled": metrics_collector is not None}

@app.get("/metrics/calls/{call_id}")
async def get_call_metrics(call_id: str):
    """Get all metrics for a specific call"""
    if not metrics_collector:
        raise HTTPException(status_code=503, detail="Metrics collection not available")
    
    try:
        metrics = await metrics_collector.get_call_metrics(call_id)
        return JSONResponse(content=metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/calls/{call_id}/summary")
async def get_call_summary(call_id: str):
    """Get metrics summary for a specific call"""
    if not metrics_collector:
        raise HTTPException(status_code=503, detail="Metrics collection not available")
    
    try:
        summary = await metrics_collector.get_call_summary(call_id)
        return JSONResponse(content=summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/calls/{call_id}/{metric_type}")
async def get_call_metrics_by_type(
    call_id: str, 
    metric_type: str,
    limit: Optional[int] = Query(None, description="Limit number of results")
):
    """Get specific type of metrics for a call"""
    if not metrics_collector:
        raise HTTPException(status_code=503, detail="Metrics collection not available")
    
    if metric_type not in ["llm", "tts", "asr", "eou"]:
        raise HTTPException(status_code=400, detail="Invalid metric type")
    
    try:
        all_metrics = await metrics_collector.get_call_metrics(call_id)
        metrics = all_metrics.get(metric_type, [])
        
        if limit:
            metrics = metrics[:limit]
        
        return JSONResponse(content={"metrics": metrics, "count": len(metrics)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/analytics/performance")
async def get_performance_analytics(
    call_id: Optional[str] = Query(None, description="Filter by call ID"),
    metric_type: Optional[str] = Query(None, description="Filter by metric type")
):
    """Get performance analytics across calls"""
    if not metrics_collector:
        raise HTTPException(status_code=503, detail="Metrics collection not available")
    
    try:
        if call_id:
            metrics = await metrics_collector.get_call_metrics(call_id)
        else:
            # Get all metrics (this might be expensive for large datasets)
            metrics = await metrics_collector.storage.get_metrics()
            # Group by metric type
            grouped_metrics = {"llm": [], "tts": [], "asr": [], "eou": []}
            for metric in metrics:
                mtype = metric.get("metric_type")
                if mtype in grouped_metrics:
                    grouped_metrics[mtype].append(metric)
            metrics = grouped_metrics
        
        analytics = {}
        
        # LLM Analytics
        if not metric_type or metric_type == "llm":
            llm_metrics = metrics.get("llm", [])
            if llm_metrics:
                ttfts = [m["ttft"] for m in llm_metrics]
                total_times = [m["total_time"] for m in llm_metrics]
                analytics["llm"] = {
                    "count": len(llm_metrics),
                    "avg_ttft": sum(ttfts) / len(ttfts),
                    "p95_ttft": sorted(ttfts)[int(len(ttfts) * 0.95)] if len(ttfts) > 1 else ttfts[0],
                    "avg_total_time": sum(total_times) / len(total_times),
                    "total_input_tokens": sum(m["input_tokens"] for m in llm_metrics),
                    "total_output_tokens": sum(m["output_tokens"] for m in llm_metrics),
                }
        
        # TTS Analytics
        if not metric_type or metric_type == "tts":
            tts_metrics = metrics.get("tts", [])
            if tts_metrics:
                ttfbs = [m["ttfb"] for m in tts_metrics]
                durations = [m["audio_duration"] for m in tts_metrics]
                analytics["tts"] = {
                    "count": len(tts_metrics),
                    "avg_ttfb": sum(ttfbs) / len(ttfbs),
                    "p95_ttfb": sorted(ttfbs)[int(len(ttfbs) * 0.95)] if len(ttfbs) > 1 else ttfbs[0],
                    "total_audio_duration": sum(durations),
                }
        
        # ASR Analytics
        if not metric_type or metric_type == "asr":
            asr_metrics = metrics.get("asr", [])
            if asr_metrics:
                processing_times = [m["processing_time"] for m in asr_metrics]
                analytics["asr"] = {
                    "count": len(asr_metrics),
                    "avg_processing_time": sum(processing_times) / len(processing_times),
                    "p95_processing_time": sorted(processing_times)[int(len(processing_times) * 0.95)] if len(processing_times) > 1 else processing_times[0],
                }
        
        # EOU Analytics
        if not metric_type or metric_type == "eou":
            eou_metrics = metrics.get("eou", [])
            if eou_metrics:
                delays = [m["eou_delay"] for m in eou_metrics]
                analytics["eou"] = {
                    "count": len(eou_metrics),
                    "avg_delay": sum(delays) / len(delays),
                    "p95_delay": sorted(delays)[int(len(delays) * 0.95)] if len(delays) > 1 else delays[0],
                }
        
        return JSONResponse(content=analytics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/metrics/test")
async def create_test_metrics():
    """Create test metrics for development/testing"""
    if not metrics_collector:
        raise HTTPException(status_code=503, detail="Metrics collection not available")
    
    try:
        # Set a test call ID
        test_call_id = "test_call_123"
        metrics_collector.set_call_id(test_call_id)
        
        # Create sample metrics
        await metrics_collector.record_llm_metric(
            ttft=0.245,
            input_tokens=50,
            output_tokens=25,
            model="gpt-4o",
            total_time=1.2
        )
        
        await metrics_collector.record_tts_metric(
            ttfb=0.150,
            audio_duration=2.5,
            text_length=25,
            model="eleven_turbo_v2_5",
            voice_id="Rachel"
        )
        
        await metrics_collector.record_asr_metric(
            audio_duration=3.0,
            processing_time=0.5,
            text_length=50,
            model="nova-2",
            language="en"
        )
        
        await metrics_collector.record_eou_metric(
            eou_delay=0.3,
            confidence=0.95
        )
        
        return {"message": "Test metrics created", "call_id": test_call_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting LiveKit Agent Metrics API")
    print("📊 Endpoints:")
    print("  - GET /health")
    print("  - GET /metrics/calls/{call_id}")
    print("  - GET /metrics/calls/{call_id}/summary")
    print("  - GET /metrics/calls/{call_id}/{metric_type}")
    print("  - GET /metrics/analytics/performance")
    print("  - POST /metrics/test")
    
    uvicorn.run(app, host="0.0.0.0", port=1236)