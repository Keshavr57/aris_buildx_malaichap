#!/usr/bin/env python3
"""Simple server starter script."""
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting AI Assistant API Server...")
    print("   API Server: http://localhost:8000")
    print("   API Docs: http://localhost:8000/docs")
    print("   React Frontend: cd frontend && npm start")
    print("   Press Ctrl+C to stop")
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )