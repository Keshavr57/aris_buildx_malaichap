"""Configuration management for hackathon AI assistant."""
import os
from typing import Optional
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    # Groq API
    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"  # Fast model
    
    # Performance
    max_tokens: int = 1024
    temperature: float = 0.1
    timeout_seconds: int = 30
    max_retries: int = 2
    
    # Cache
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 3600  # 1 hour
    
    # RAG
    chroma_persist_dir: str = "./chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"  # Fast embeddings
    max_rag_results: int = 3
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

config = Config()