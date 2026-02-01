"""User-based conversational memory with Redis persistence."""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import redis.asyncio as redis

from .config import config

logger = logging.getLogger(__name__)

class ConversationMemory:
    def __init__(self):
        self.redis_client = None
        self.max_history = 20  # Keep last 20 messages for context
        self._memory_fallback = {}  # In-memory fallback
    
    async def _init_redis(self):
        """Initialize Redis for memory persistence."""
        if self.redis_client:
            return
            
        try:
            self.redis_client = redis.from_url(config.redis_url)
            await self.redis_client.ping()
            logger.info("Memory storage connected")
        except Exception as e:
            logger.warning(f"Memory storage unavailable: {e}")
            self.redis_client = None
    
    def _memory_key(self, user_id: str) -> str:
        """Generate memory key for user."""
        return f"memory:user:{user_id}"
    
    async def add_message(self, user_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        """Add message to user's conversation history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        await self._init_redis()
        
        try:
            key = self._memory_key(user_id)
            
            # Get existing history
            history = []
            if self.redis_client:
                try:
                    history_json = await self.redis_client.get(key)
                    history = json.loads(history_json) if history_json else []
                except Exception as e:
                    logger.warning(f"Redis read error: {e}")
            
            # Fallback to in-memory
            if not history and user_id in self._memory_fallback:
                history = self._memory_fallback[user_id]
            
            # Add new message
            history.append(message)
            
            # Trim to max_history
            if len(history) > self.max_history:
                history = history[-self.max_history:]
            
            # Save to Redis
            if self.redis_client:
                try:
                    await self.redis_client.setex(
                        key, 
                        config.cache_ttl * 24,  # 24 hours for memory
                        json.dumps(history)
                    )
                except Exception as e:
                    logger.warning(f"Redis write error: {e}")
            
            # Always save to fallback
            self._memory_fallback[user_id] = history
            
        except Exception as e:
            logger.warning(f"Memory save error: {e}")
    
    async def get_history(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get user's conversation history."""
        await self._init_redis()
        
        try:
            key = self._memory_key(user_id)
            history = []
            
            # Try Redis first
            if self.redis_client:
                try:
                    history_json = await self.redis_client.get(key)
                    if history_json:
                        history = json.loads(history_json)
                except Exception as e:
                    logger.warning(f"Redis read error: {e}")
            
            # Fallback to in-memory
            if not history and user_id in self._memory_fallback:
                history = self._memory_fallback[user_id]
            
            if limit:
                history = history[-limit:]
            
            return history
            
        except Exception as e:
            logger.warning(f"Memory read error: {e}")
            return []
    
    async def get_context_messages(self, user_id: str) -> List[Dict]:
        """Get messages formatted for LLM context."""
        history = await self.get_history(user_id, limit=10)  # Last 10 for context
        
        # Convert to LLM format
        messages = []
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return messages
    
    async def clear_session(self, user_id: str):
        """Clear user's memory."""
        await self._init_redis()
        
        try:
            key = self._memory_key(user_id)
            if self.redis_client:
                await self.redis_client.delete(key)
            
            # Clear fallback memory too
            if user_id in self._memory_fallback:
                del self._memory_fallback[user_id]
                
        except Exception as e:
            logger.warning(f"Memory clear error: {e}")

# Global instance
memory = ConversationMemory()