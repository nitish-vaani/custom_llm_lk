import time
import asyncio
import logging
from typing import Optional
from livekit.plugins import openai, deepgram, elevenlabs

from .metrics_collector import MetricsCollector

logger = logging.getLogger("metrics-wrapper")

class MetricsLLMWrapper:
    """Lightweight wrapper for LLM that collects metrics without breaking LiveKit interface"""
    
    def __init__(self, llm, metrics_collector: Optional[MetricsCollector] = None):
        self.llm = llm
        self.metrics_collector = metrics_collector
        self.model = getattr(llm, 'model', 'unknown')
        
        # Debug: Check what methods the LLM actually has
        llm_methods = [method for method in dir(llm) if not method.startswith('_')]
        logger.debug(f"🔍 LLM methods available: {llm_methods}")
        
        # Find the correct generation method
        self._generation_method = None
        self._original_method = None
        
        # Common method names in LiveKit LLMs
        possible_methods = ['agenerate', 'generate', 'chat', 'achat', 'stream', 'astream']
        
        for method_name in possible_methods:
            if hasattr(llm, method_name):
                self._generation_method = method_name
                self._original_method = getattr(llm, method_name)
                logger.debug(f"🎯 Found generation method: {method_name}")
                break
        
        # If we found a generation method and have metrics collector, wrap it
        if self._generation_method and metrics_collector:
            setattr(llm, self._generation_method, self._create_wrapped_method())
            logger.debug(f"✅ Wrapped {self._generation_method} with metrics")
    
    def _create_wrapped_method(self):
        """Create a wrapped version of the generation method"""
        async def wrapped_method(*args, **kwargs):
            return self._generate_with_metrics(*args, **kwargs)
        
        # For non-async methods, create a non-async wrapper
        if not asyncio.iscoroutinefunction(self._original_method):
            def wrapped_method(*args, **kwargs):
                return self._generate_with_metrics_sync(*args, **kwargs)
        
        return wrapped_method
    
    async def _generate_with_metrics(self, *args, **kwargs):
        """Async generator with metrics collection"""
        start_time = time.time()
        ttft_recorded = False
        input_tokens = 0
        output_tokens = 0
        ttft = 0
        
        # Better input token estimation
        if args:
            first_arg = args[0]
            logger.debug(f"🔍 First arg type: {type(first_arg)}, content: {str(first_arg)[:100]}...")
            
            if hasattr(first_arg, 'messages'):
                # Chat completion format
                try:
                    messages_text = ""
                    for msg in first_arg.messages:
                        if hasattr(msg, 'content'):
                            messages_text += str(msg.content) + " "
                        else:
                            messages_text += str(msg) + " "
                    input_tokens = len(messages_text.split()) * 1.3
                    logger.debug(f"🔍 Extracted {len(messages_text)} chars, estimated {input_tokens} tokens")
                except Exception as e:
                    logger.debug(f"🔍 Error extracting from messages: {e}")
            elif isinstance(first_arg, str):
                input_tokens = len(first_arg.split()) * 1.3
                logger.debug(f"🔍 String input: {len(first_arg)} chars, estimated {input_tokens} tokens")
            else:
                # Try to extract text from object
                text_content = str(first_arg)
                input_tokens = len(text_content.split()) * 1.3
                logger.debug(f"🔍 Generic object: {len(text_content)} chars, estimated {input_tokens} tokens")
        
        # Check if original method is async generator
        if asyncio.iscoroutinefunction(self._original_method):
            result = self._original_method(*args, **kwargs)
            if hasattr(result, '__aiter__'):
                # It's an async generator - yield chunks
                full_response = ""
                async for chunk in result:
                    if not ttft_recorded:
                        ttft = time.time() - start_time
                        ttft_recorded = True
                        logger.debug(f"🔍 TTFT recorded: {ttft:.3f}s")
                    
                    # Extract and accumulate text from chunk
                    chunk_text = self._extract_text_from_chunk(chunk)
                    if chunk_text:
                        full_response += chunk_text
                        logger.debug(f"🔍 Chunk text: '{chunk_text}' (total: {len(full_response)} chars)")
                    
                    yield chunk
                    
                # Calculate output tokens from full response
                if full_response:
                    output_tokens = len(full_response.split()) * 1.3
                    logger.debug(f"🔍 Full response: {len(full_response)} chars, estimated {output_tokens} tokens")
                    
                # Record metrics after streaming is complete
                total_time = time.time() - start_time
                if self.metrics_collector:
                    logger.debug(f"🔍 Recording metrics: TTFT={ttft:.3f}s, in={input_tokens}, out={output_tokens}, total={total_time:.3f}s")
                    asyncio.create_task(
                        self.metrics_collector.record_llm_metric(
                            ttft=ttft if ttft_recorded else total_time,
                            input_tokens=int(input_tokens),
                            output_tokens=int(output_tokens),
                            model=self.model,
                            total_time=total_time
                        )
                    )
            else:
                # It's a regular async method - await and yield single result
                result_data = await result
                total_time = time.time() - start_time
                text_content = self._extract_text_from_chunk(result_data)
                if text_content:
                    output_tokens = len(text_content.split()) * 1.3
                    logger.debug(f"🔍 Single response: '{text_content}', estimated {output_tokens} tokens")
                
                # Record metrics
                if self.metrics_collector:
                    logger.debug(f"🔍 Recording metrics: TTFT={total_time:.3f}s, in={input_tokens}, out={output_tokens}")
                    asyncio.create_task(
                        self.metrics_collector.record_llm_metric(
                            ttft=total_time,  # For non-streaming, TTFT = total time
                            input_tokens=int(input_tokens),
                            output_tokens=int(output_tokens),
                            model=self.model,
                            total_time=total_time
                        )
                    )
                yield result_data
        else:
            # Sync method
            result = self._original_method(*args, **kwargs)
            total_time = time.time() - start_time
            
            # Handle sync generators
            if hasattr(result, '__iter__') and not isinstance(result, (str, bytes)):
                full_response = ""
                for chunk in result:
                    if not ttft_recorded:
                        ttft = time.time() - start_time
                        ttft_recorded = True
                    
                    chunk_text = self._extract_text_from_chunk(chunk)
                    if chunk_text:
                        full_response += chunk_text
                    
                    yield chunk
                    
                # Calculate output tokens
                if full_response:
                    output_tokens = len(full_response.split()) * 1.3
                    
                # Record metrics after iteration
                total_time = time.time() - start_time
                if self.metrics_collector:
                    asyncio.create_task(
                        self.metrics_collector.record_llm_metric(
                            ttft=ttft if ttft_recorded else total_time,
                            input_tokens=int(input_tokens),
                            output_tokens=int(output_tokens),
                            model=self.model,
                            total_time=total_time
                        )
                    )
            else:
                # Regular sync return - yield single result
                text_content = self._extract_text_from_chunk(result)
                if text_content:
                    output_tokens = len(text_content.split()) * 1.3
                
                # Record metrics
                if self.metrics_collector:
                    asyncio.create_task(
                        self.metrics_collector.record_llm_metric(
                            ttft=total_time,
                            input_tokens=int(input_tokens),
                            output_tokens=int(output_tokens),
                            model=self.model,
                            total_time=total_time
                        )
                    )
                yield result
    
    def _generate_with_metrics_sync(self, *args, **kwargs):
        """Sync wrapper for non-async methods"""
        start_time = time.time()
        result = self._original_method(*args, **kwargs)
        total_time = time.time() - start_time
        
        # Estimate tokens
        input_tokens = 0
        if args and isinstance(args[0], str):
            input_tokens = len(args[0].split()) * 1.3
        
        output_tokens = 0
        text_content = self._extract_text_from_chunk(result)
        if text_content:
            output_tokens = len(text_content.split()) * 1.3
        
        # Record metrics
        if self.metrics_collector:
            asyncio.create_task(
                self.metrics_collector.record_llm_metric(
                    ttft=total_time,
                    input_tokens=int(input_tokens),
                    output_tokens=int(output_tokens),
                    model=self.model,
                    total_time=total_time
                )
            )
        
        return result
    
    def _extract_text_from_chunk(self, chunk):
        """Extract text content from various chunk formats"""
        if isinstance(chunk, str):
            return chunk
        elif hasattr(chunk, 'content') and chunk.content:
            return str(chunk.content)
        elif hasattr(chunk, 'delta') and chunk.delta:
            return str(chunk.delta)
        elif hasattr(chunk, 'text') and chunk.text:
            return str(chunk.text)
        elif hasattr(chunk, 'message') and chunk.message:
            if hasattr(chunk.message, 'content'):
                return str(chunk.message.content)
        return ""
    
    def __getattr__(self, name):
        """Delegate everything else to the original LLM"""
        return getattr(self.llm, name)
    
    def __setattr__(self, name, value):
        """Handle attribute setting properly"""
        if name in ['llm', 'metrics_collector', 'model', '_generation_method', '_original_method']:
            super().__setattr__(name, value)
        else:
            setattr(self.llm, name, value)
    
    def unwrap(self):
        """Restore original LLM if needed"""
        if self._generation_method and self._original_method:
            setattr(self.llm, self._generation_method, self._original_method)
        return self.llm

class MetricsTTSWrapper:
    """Wrapper for TTS that collects metrics"""
    
    def __init__(self, tts, metrics_collector: Optional[MetricsCollector] = None):
        self.tts = tts
        self.metrics_collector = metrics_collector
        logger.info(f"🔍 TTS wrapper initialized for {type(tts)}")
        
        # Safely extract model and voice_id from TTS options
        if hasattr(tts, '_opts'):
            self.model = getattr(tts._opts, 'model', 'unknown')
            self.voice_id = getattr(tts._opts, 'voice_id', 'unknown')
            logger.info(f"🔍 TTS model: {self.model}, voice: {self.voice_id}")
        else:
            self.model = 'unknown'
            self.voice_id = 'unknown'
            logger.info(f"🔍 TTS no _opts found, using defaults")
        
        # Wrap all possible TTS methods
        for method_name in ['synthesize', 'asynthesize', 'stream', 'speak']:
            if hasattr(tts, method_name):
                original_method = getattr(tts, method_name)
                wrapped_method = self._wrap_tts_method(original_method, method_name)
                setattr(tts, method_name, wrapped_method)
                logger.info(f"🔍 TTS {method_name} method wrapped")
    
    def _wrap_tts_method(self, original_method, method_name):
        """Wrap a TTS method to collect metrics"""
        def wrapped_method(*args, **kwargs):
            logger.info(f"🔍 TTS {method_name} called with args: {len(args)}, kwargs: {list(kwargs.keys())}")
            
            # Extract text from arguments
            text = ""
            if args:
                text = str(args[0])
            
            logger.info(f"🔍 TTS text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            start_time = time.time()
            text_length = len(text)
            
            # Call original method
            result = original_method(*args, **kwargs)
            
            # If it returns a stream, wrap it
            if hasattr(result, '__aiter__'):
                return self._wrap_tts_stream(result, start_time, text_length, text)
            elif hasattr(result, '__iter__') and not isinstance(result, (str, bytes)):
                return self._wrap_tts_iterator(result, start_time, text_length, text)
            else:
                # Direct result - record metrics immediately
                total_time = time.time() - start_time
                if self.metrics_collector:
                    asyncio.create_task(
                        self.metrics_collector.record_tts_metric(
                            ttfb=total_time,
                            audio_duration=text_length * 0.1,  # Rough estimate
                            text_length=text_length,
                            model=self.model,
                            voice_id=self.voice_id
                        )
                    )
                    logger.info(f"🔍 TTS direct metrics recorded: time={total_time:.3f}s")
                return result
        
        return wrapped_method
    
    def _wrap_tts_stream(self, original_stream, start_time, text_length, text):
        """Wrap TTS async stream"""
        class MetricsTTSStream:
            def __init__(self, stream, wrapper):
                self.stream = stream
                self.wrapper = wrapper
                self.start_time = start_time
                self.ttfb_recorded = False
                self.text_length = text_length
                logger.info(f"🔍 TTS async stream created for: '{text[:30]}...'")
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                try:
                    chunk = await self.stream.__anext__()
                    
                    if not self.ttfb_recorded:
                        ttfb = time.time() - self.start_time
                        self.ttfb_recorded = True
                        logger.info(f"🔍 TTS TTFB: {ttfb:.3f}s")
                        
                        # Estimate audio duration
                        audio_duration = self.text_length * 0.1  # Rough estimate
                        
                        # Record metrics
                        if self.wrapper.metrics_collector:
                            asyncio.create_task(
                                self.wrapper.metrics_collector.record_tts_metric(
                                    ttfb=ttfb,
                                    audio_duration=audio_duration,
                                    text_length=self.text_length,
                                    model=self.wrapper.model,
                                    voice_id=self.wrapper.voice_id
                                )
                            )
                            logger.info(f"🔍 TTS stream metrics recorded")
                    
                    return chunk
                except StopAsyncIteration:
                    logger.info(f"🔍 TTS stream ended")
                    raise
                except Exception as e:
                    logger.error(f"🔍 TTS stream error: {e}")
                    raise
        
        return MetricsTTSStream(original_stream, self)
    
    def _wrap_tts_iterator(self, original_iterator, start_time, text_length, text):
        """Wrap TTS sync iterator"""
        logger.info(f"🔍 TTS sync iterator created for: '{text[:30]}...'")
        ttfb_recorded = False
        
        def generator():
            nonlocal ttfb_recorded
            for chunk in original_iterator:
                if not ttfb_recorded:
                    ttfb = time.time() - start_time
                    ttfb_recorded = True
                    logger.info(f"🔍 TTS sync TTFB: {ttfb:.3f}s")
                    
                    # Record metrics
                    if self.metrics_collector:
                        asyncio.create_task(
                            self.metrics_collector.record_tts_metric(
                                ttfb=ttfb,
                                audio_duration=text_length * 0.1,
                                text_length=text_length,
                                model=self.model,
                                voice_id=self.voice_id
                            )
                        )
                        logger.info(f"🔍 TTS sync metrics recorded")
                
                yield chunk
        
        return generator()
    
    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped TTS"""
        if name in ['synthesize', 'asynthesize', 'stream', 'speak']:
            logger.info(f"🔍 TTS {name} method accessed")
        return getattr(self.tts, name)

class MetricsASRWrapper:
    """Wrapper for ASR that collects metrics"""
    
    def __init__(self, stt, metrics_collector: Optional[MetricsCollector] = None):
        self.stt = stt
        self.metrics_collector = metrics_collector
        logger.info(f"🔍 ASR wrapper initialized for {type(stt)}")
        
        # Better way to extract model and language from Deepgram STT
        self.model = getattr(stt, '_model', 'unknown')
        self.language = getattr(stt, '_language', 'unknown')
        
        # Try alternative attribute names
        if hasattr(stt, '_opts'):
            self.model = getattr(stt._opts, 'model', self.model)
            self.language = getattr(stt._opts, 'language', self.language)
        
        logger.info(f"🔍 ASR model: {self.model}, language: {self.language}")
        
        # Wrap the stream method since that's what's being called
        if hasattr(stt, 'stream'):
            original_stream = stt.stream
            stt.stream = self._wrap_stream_method(original_stream)
            logger.info(f"🔍 ASR stream method wrapped")
    
    def _wrap_stream_method(self, original_stream):
        """Wrap the stream method to collect metrics"""
        def wrapped_stream(*args, **kwargs):
            logger.info(f"🔍 ASR stream called with args: {len(args)}, kwargs: {list(kwargs.keys())}")
            
            # Call original and wrap the returned stream
            original_result = original_stream(*args, **kwargs)
            return self._wrap_recognition_stream(original_result)
        
        return wrapped_stream
    
    def _wrap_recognition_stream(self, original_stream):
        """Wrap the recognition stream to collect metrics"""
        class MetricsRecognitionStream:
            def __init__(self, stream, wrapper):
                self.stream = stream
                self.wrapper = wrapper
                self.start_time = time.time()
                self.audio_duration = 0.0
                logger.info(f"🔍 ASR recognition stream created")
            
            # Implement async context manager protocol
            async def __aenter__(self):
                logger.info(f"🔍 ASR stream entering context")
                if hasattr(self.stream, '__aenter__'):
                    self.stream_context = await self.stream.__aenter__()
                    return self
                else:
                    return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                logger.info(f"🔍 ASR stream exiting context")
                if hasattr(self.stream, '__aexit__'):
                    return await self.stream.__aexit__(exc_type, exc_val, exc_tb)
                return False
            
            def __aiter__(self):
                # Return the actual stream's iterator if it has one
                if hasattr(self.stream, '__aiter__'):
                    return self._wrap_iterator(self.stream.__aiter__())
                else:
                    return self
            
            def _wrap_iterator(self, iterator):
                """Wrap the actual iterator to collect metrics"""
                class MetricsIterator:
                    def __init__(self, orig_iter, wrapper_stream):
                        self.orig_iter = orig_iter
                        self.wrapper_stream = wrapper_stream
                    
                    def __aiter__(self):
                        return self
                    
                    async def __anext__(self):
                        try:
                            result = await self.orig_iter.__anext__()
                            
                            # Extract metrics from recognition result
                            if hasattr(result, 'alternatives') and result.alternatives:
                                processing_time = time.time() - self.wrapper_stream.start_time
                                text = result.alternatives[0].transcript
                                text_length = len(text)
                                
                                # Estimate audio duration (rough)
                                self.wrapper_stream.audio_duration = processing_time * 2  # Rough estimate
                                
                                logger.info(f"🔍 ASR result: '{text}' (len={text_length}, time={processing_time:.3f}s)")
                                
                                # Record metrics
                                if self.wrapper_stream.wrapper.metrics_collector:
                                    asyncio.create_task(
                                        self.wrapper_stream.wrapper.metrics_collector.record_asr_metric(
                                            audio_duration=self.wrapper_stream.audio_duration,
                                            processing_time=processing_time,
                                            text_length=text_length,
                                            model=self.wrapper_stream.wrapper.model,
                                            language=self.wrapper_stream.wrapper.language
                                        )
                                    )
                                    logger.info(f"🔍 ASR metrics recorded")
                            
                            return result
                        except StopAsyncIteration:
                            logger.info(f"🔍 ASR iterator ended")
                            raise
                        except Exception as e:
                            logger.error(f"🔍 ASR iterator error: {e}")
                            raise
                
                return MetricsIterator(iterator, self)
            
            async def __anext__(self):
                try:
                    # If stream_context exists, use it, otherwise use self.stream
                    stream_to_use = getattr(self, 'stream_context', self.stream)
                    result = await stream_to_use.__anext__()
                    
                    # Extract metrics from recognition result
                    if hasattr(result, 'alternatives') and result.alternatives:
                        processing_time = time.time() - self.start_time
                        text = result.alternatives[0].transcript
                        text_length = len(text)
                        
                        # Estimate audio duration (rough)
                        self.audio_duration = processing_time * 2  # Rough estimate
                        
                        logger.info(f"🔍 ASR result: '{text}' (len={text_length}, time={processing_time:.3f}s)")
                        
                        # Record metrics
                        if self.wrapper.metrics_collector:
                            asyncio.create_task(
                                self.wrapper.metrics_collector.record_asr_metric(
                                    audio_duration=self.audio_duration,
                                    processing_time=processing_time,
                                    text_length=text_length,
                                    model=self.wrapper.model,
                                    language=self.wrapper.language
                                )
                            )
                            logger.info(f"🔍 ASR metrics recorded")
                    
                    return result
                except StopAsyncIteration:
                    logger.info(f"🔍 ASR stream ended")
                    raise
                except Exception as e:
                    logger.error(f"🔍 ASR stream error: {e}")
                    raise
        
        return MetricsRecognitionStream(original_stream, self)
    
    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped STT"""
        if name in ['recognize', 'arecognize', 'stream']:
            logger.info(f"🔍 ASR {name} method accessed")
        return getattr(self.stt, name)
    
    def recognize(self, *args, **kwargs):
        """Wrapper for recognition with metrics"""
        if not self.metrics_collector:
            return self.stt.recognize(*args, **kwargs)
        
        start_time = time.time()
        
        class MetricsSTTStream:
            def __init__(self, original_stream, wrapper_instance):
                self.original_stream = original_stream
                self.wrapper = wrapper_instance
                self.start_time = start_time
                self.audio_duration = 0.0
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                result = await self.original_stream.__anext__()
                
                processing_time = time.time() - self.start_time
                
                # Extract metrics from result
                if hasattr(result, 'alternatives') and result.alternatives:
                    text = result.alternatives[0].transcript
                    text_length = len(text)
                    
                    # Estimate audio duration (would need actual audio length)
                    self.audio_duration = processing_time * 2  # Rough estimate
                    
                    # Record metrics
                    asyncio.create_task(
                        self.wrapper.metrics_collector.record_asr_metric(
                            audio_duration=self.audio_duration,
                            processing_time=processing_time,
                            text_length=text_length,
                            model=self.wrapper.model,
                            language=self.wrapper.language
                        )
                    )
                
                return result
        
        original_stream = self.stt.recognize(*args, **kwargs)
        return MetricsSTTStream(original_stream, self)

def wrap_with_metrics(component, component_type: str, metrics_collector: Optional[MetricsCollector] = None):
    """Factory function to wrap components with metrics collection"""
    if not metrics_collector:
        return component
    
    if component_type == "llm":
        logger.info("🔍 LLM wrapping enabled - this will provide real LLM metrics")
        try:
            return MetricsLLMWrapper(component, metrics_collector)
        except Exception as e:
            logger.error(f"🔍 LLM wrapping failed: {e}")
            return component
    elif component_type == "tts":
        logger.info("🔍 TTS using event-based metrics (simulated but working)")
        return component  # Keep using event-based metrics
    elif component_type == "stt":
        logger.info("🔍 STT using event-based metrics (simulated but working)")
        return component  # Keep using event-based metrics
    else:
        return component

