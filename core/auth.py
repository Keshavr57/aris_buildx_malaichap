"""User authentication and session management."""
import uuid
import hashlib
import json
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import redis.asyncio as redis

from .config import config

logger = logging.getLogger(__name__)

class UserAuth:
    def __init__(self):
        self.redis_client = None
        self.sessions = {}  # Fallback in-memory storage
        self.users = {}     # Fallback user storage
        
    async def _init_redis(self):
        """Initialize Redis connection."""
        if self.redis_client:
            return
            
        try:
            self.redis_client = redis.from_url(config.redis_url)
            await self.redis_client.ping()
            logger.info("Auth Redis connected")
        except Exception as e:
            logger.warning(f"Auth Redis unavailable: {e}")
            self.redis_client = None
    
    def _hash_password(self, password: str) -> str:
        """Hash password for storage."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    async def register_user(self, username: str, password: str) -> Dict:
        """Register a new user."""
        await self._init_redis()
        
        user_id = str(uuid.uuid4())
        user_data = {
            "user_id": user_id,
            "username": username,
            "password_hash": self._hash_password(password),
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None
        }
        
        # Store user data
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    f"user:{username}",
                    config.cache_ttl * 24 * 7,  # 1 week
                    json.dumps(user_data)
                )
            except Exception as e:
                logger.error(f"Failed to store user in Redis: {e}")
        
        # Always store in fallback memory
        self.users[username] = user_data
        
        return {"user_id": user_id, "username": username, "status": "registered"}
    
    async def login_user(self, username: str, password: str) -> Dict:
        """Login user and create session."""
        await self._init_redis()
        
        # Get user data
        user_data = None
        if self.redis_client:
            try:
                user_json = await self.redis_client.get(f"user:{username}")
                if user_json:
                    user_data = json.loads(user_json)
            except Exception as e:
                logger.error(f"Failed to get user from Redis: {e}")
        
        # Fallback to memory
        if not user_data and username in self.users:
            user_data = self.users[username]
        
        if not user_data:
            return {"error": "User not found"}
        
        # Verify password
        if user_data["password_hash"] != self._hash_password(password):
            return {"error": "Invalid password"}
        
        # Create session
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": user_data["user_id"],
            "username": username,
            "login_time": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }
        
        # Store session
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    f"session:{session_id}",
                    config.cache_ttl * 24,  # 24 hours
                    json.dumps(session_data)
                )
            except Exception as e:
                logger.error(f"Failed to store session in Redis: {e}")
        
        # Always store in fallback memory
        self.sessions[session_id] = session_data
        
        # Update last login
        user_data["last_login"] = datetime.utcnow().isoformat()
        self.users[username] = user_data
        
        return {
            "session_id": session_id,
            "user_id": user_data["user_id"],
            "username": username,
            "status": "logged_in"
        }
    
    async def get_user_from_session(self, session_id: str) -> Optional[Dict]:
        """Get user data from session ID."""
        await self._init_redis()
        
        # Get session data
        session_data = None
        if self.redis_client:
            try:
                session_json = await self.redis_client.get(f"session:{session_id}")
                if session_json:
                    session_data = json.loads(session_json)
            except Exception as e:
                logger.error(f"Failed to get session from Redis: {e}")
        
        # Fallback to memory
        if not session_data and session_id in self.sessions:
            session_data = self.sessions[session_id]
        
        if not session_data:
            return None
        
        # Check if session is expired
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if datetime.utcnow() > expires_at:
            return None
        
        return {
            "user_id": session_data["user_id"],
            "username": session_data["username"],
            "session_id": session_id
        }
    
    async def logout_user(self, session_id: str) -> Dict:
        """Logout user and destroy session."""
        await self._init_redis()
        
        if self.redis_client:
            try:
                await self.redis_client.delete(f"session:{session_id}")
            except Exception as e:
                logger.error(f"Failed to delete session from Redis: {e}")
        
        # Remove from memory fallback
        if session_id in self.sessions:
            del self.sessions[session_id]

# Global instance
auth = UserAuth()