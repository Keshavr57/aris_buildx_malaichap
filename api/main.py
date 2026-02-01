"""FastAPI server for hackathon AI assistant with authentication and file uploads."""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.agent import agent
from core.rag import rag
from core.auth import auth
from core.file_processor import file_processor
from core.config import config

# Configure logging
logging.basicConfig(level=config.log_level)
logger = logging.getLogger(__name__)

# Request models
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    file_context: bool = True  # Include file context in response

class DocumentRequest(BaseModel):
    content: str
    metadata: Optional[dict] = None

# Dependency to get current user
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current user from session token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    session_id = authorization.replace("Bearer ", "")
    user = await auth.get_user_from_session(session_id)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    return user

# Startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown."""
    logger.info("🚀 AI Assistant starting up...")
    
    # Initialize components
    await asyncio.gather(
        agent.get_status(),  # Warm up agent
        return_exceptions=True
    )
    
    logger.info("✅ AI Assistant ready!")
    yield
    
    logger.info("🛑 AI Assistant shutting down...")

# Create app
app = FastAPI(
    title="Hackathon AI Assistant",
    description="Fast, reliable AI assistant with tools, RAG, and memory",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check."""
    return {"status": "ready", "message": "Hackathon AI Assistant"}

@app.get("/status")
async def get_status():
    """Get system status."""
    return await agent.get_status()

@app.post("/register")
async def register(request: RegisterRequest):
    """Register a new user."""
    try:
        result = await auth.register_user(request.username, request.password)
        return result
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
async def login(request: LoginRequest):
    """Login user and get session token."""
    try:
        result = await auth.login_user(request.username, request.password)
        if "error" in result:
            raise HTTPException(status_code=401, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout user and destroy session."""
    try:
        result = await auth.logout_user(current_user["session_id"])
        return result
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Main chat endpoint."""
    try:
        user_id = current_user["user_id"]
        
        if request.stream:
            # Streaming response
            async def generate():
                async for chunk in agent.stream_response(request.message, user_id):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/plain",
                headers={"X-User-ID": user_id}
            )
        else:
            # Regular response
            response = await agent.process_message(request.message, user_id)
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents")
async def add_document(request: DocumentRequest, current_user: dict = Depends(get_current_user)):
    """Add document to knowledge base."""
    try:
        success = await rag.add_document(request.content, request.metadata)
        if success:
            return {"status": "added", "message": "Document added to knowledge base"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add document")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document add error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/search")
async def search_documents(query: str, limit: int = 3, current_user: dict = Depends(get_current_user)):
    """Search knowledge base."""
    try:
        results = await rag.query(query, limit)
        return {"results": results}
    except Exception as e:
        logger.error(f"Document search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload and process multiple files."""
    try:
        processed_files = []
        
        for file in files:
            # Read file content
            content = await file.read()
            
            # Process file
            result = await file_processor.process_file(
                content, 
                file.filename, 
                file.content_type or ""
            )
            
            processed_files.append({
                "filename": file.filename,
                "type": result.get("type", "unknown"),
                "file_id": result.get("file_id"),
                "status": "success" if not result.get("error") else "error",
                "error": result.get("error"),
                "size": len(content)
            })
        
        return {
            "files": processed_files,
            "message": f"{len(processed_files)} file(s) uploaded successfully"
        }
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files")
async def get_uploaded_files(current_user: dict = Depends(get_current_user)):
    """Get list of uploaded files."""
    try:
        files = file_processor.get_file_context(current_user["user_id"])
        return {
            "files": [
                {
                    "filename": f.get("filename"),
                    "type": f.get("type"),
                    "file_id": f.get("file_id"),
                    "processed_at": f.get("processed_at")
                }
                for f in files
            ]
        }
    except Exception as e:
        logger.error(f"Get files error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=config.log_level.lower()
    )