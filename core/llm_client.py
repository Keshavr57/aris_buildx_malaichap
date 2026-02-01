"""Optimized Groq LLM client with caching and fallbacks."""
import asyncio
import hashlib
import json
import logging
from typing import Dict, List, Optional, AsyncGenerator
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential
import redis.asyncio as redis

from .config import config

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.client = AsyncGroq(api_key=config.groq_api_key)
        self.redis_client = None
    
    async def _init_redis(self):
        """Initialize Redis connection for caching."""
        try:
            self.redis_client = redis.from_url(config.redis_url)
            await self.redis_client.ping()
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
            self.redis_client = None
    
    def _cache_key(self, messages: List[Dict], tools: Optional[List] = None) -> str:
        """Generate cache key for request."""
        content = json.dumps({
            "messages": messages,
            "tools": tools or [],
            "model": config.groq_model,
            "temperature": config.temperature
        }, sort_keys=True)
        return f"llm:{hashlib.md5(content.encode()).hexdigest()}"
    
    async def _get_cached(self, cache_key: str) -> Optional[Dict]:
        """Get cached response."""
        if not self.redis_client:
            return None
        try:
            cached = await self.redis_client.get(cache_key)
            return json.loads(cached) if cached else None
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    async def _set_cache(self, cache_key: str, response: Dict):
        """Cache response."""
        if not self.redis_client:
            return
        try:
            await self.redis_client.setex(
                cache_key, 
                config.cache_ttl, 
                json.dumps(response)
            )
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    @retry(
        stop=stop_after_attempt(config.max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=4)
    )
    async def complete(
        self, 
        messages: List[Dict], 
        tools: Optional[List] = None,
        stream: bool = False
    ) -> Dict:
        """Complete chat with caching and retries."""
        cache_key = self._cache_key(messages, tools)
        
        # Check cache first (only for non-streaming)
        if not stream:
            cached = await self._get_cached(cache_key)
            if cached:
                logger.info("Cache hit")
                return cached
        
        try:
            # Make API call
            kwargs = {
                "model": config.groq_model,
                "messages": messages,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "stream": stream
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**kwargs),
                timeout=config.timeout_seconds
            )
            
            if stream:
                return response
            
            # Convert to dict for caching
            result = {
                "content": response.choices[0].message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in (response.choices[0].message.tool_calls or [])
                ]
            }
            
            # Cache non-streaming responses
            await self._set_cache(cache_key, result)
            return result
            
        except asyncio.TimeoutError:
            logger.error("LLM timeout")
            return {"content": "I'm experiencing high load. Please try again.", "tool_calls": []}
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return {"content": "I encountered an error. Please rephrase your question.", "tool_calls": []}
    
    async def stream_complete(
        self, 
        messages: List[Dict], 
        tools: Optional[List] = None
    ) -> AsyncGenerator[str, None]:
        """Stream completion with fallback."""
        try:
            response = await self.complete(messages, tools, stream=True)
            
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "I encountered an error while streaming. Please try again."

# Global instance
llm_client = LLMClient()