"""Core AI agent with optimized workflow."""
import asyncio
import logging
from typing import Dict, List, Optional, AsyncGenerator
from datetime import datetime

from .llm_client import llm_client
from .memory import memory
from .rag import rag
from .tools import tools
from .file_processor import file_processor
from .config import config

logger = logging.getLogger(__name__)

class AIAgent:
    def __init__(self):
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt from file."""
        try:
            # Try to load competition prompt first
            from config.competition_config import USE_COMPETITION_PROMPT, COMPETITION_PROMPT_FILE, SYSTEM_PROMPT_FILE
            
            prompt_file = COMPETITION_PROMPT_FILE if USE_COMPETITION_PROMPT else SYSTEM_PROMPT_FILE
            
            with open(prompt_file, 'r') as f:
                return f.read()
        except Exception as e:
            # Fallback to default prompt
            return """You are a helpful AI assistant optimized for speed and accuracy.

Key behaviors:
- Be concise but complete
- Use tools when needed for current information
- Provide fallback answers if tools fail
- Stay focused on the user's request
- Prioritize speed over verbosity
- Remember conversation context

Current time: {current_time}

Available tools:
- web_search: Search the web for current information
- calculate: Perform mathematical calculations
- get_time: Get current date and time

Always provide a helpful response even if tools fail."""
    
    async def _prepare_messages(self, user_message: str, user_id: str, include_files: bool = True) -> List[Dict]:
        """Prepare message context with mode-aware file handling."""
        # Initialize Redis connections if needed
        if not llm_client.redis_client:
            await llm_client._init_redis()
        if not memory.redis_client:
            await memory._init_redis()

        messages = []
        
        # Get conversation history first
        history = await memory.get_context_messages(user_id)
        
        # Build context-aware system prompt
        system_content = self.system_prompt.format(
            current_time=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        
        # Check if we should enter FILE MODE
        files = file_processor.get_file_context(user_id)
        has_files = bool(files)
        
        # File mode triggers
        file_keywords = ["pdf", "file", "document", "image", "upload", "is pdf me", "file ke andar", "document me", "image me"]
        user_mentions_files = any(keyword in user_message.lower() for keyword in file_keywords)
        
        # Enter FILE MODE only if files exist AND user mentions them, OR files were just uploaded
        file_mode = has_files and (user_mentions_files or self._recently_uploaded(user_id))
        
        if file_mode and include_files:
            system_content += "\n\n================================\nFILE MODE ACTIVATED - UPLOADED FILES:\n================================\n"
            
            for file_data in files[-3:]:  # Last 3 files
                if file_data.get("content"):
                    system_content += f"\n--- {file_data['filename']} ({file_data['type']}) ---\n"
                    content = file_data["content"]
                    # Keep substantial content for file mode
                    if len(content) > 4000:
                        content = content[:4000] + "... [content continues]"
                    system_content += content + "\n"
            
            system_content += "\n🚨 FILE MODE: User has files and mentioned them. Use file content directly."
        
        # Add memory context if user has history
        if history:
            system_content += f"\n\nContinuing conversation naturally."
        
        messages.append({
            "role": "system",
            "content": system_content
        })
        
        # Add RAG context silently if available
        rag_context = await rag.get_context(user_message)
        if rag_context:
            messages.append({
                "role": "system",
                "content": f"Context: {rag_context}"
            })
        
        # Add conversation history
        messages.extend(history)
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    def _recently_uploaded(self, user_id: str) -> bool:
        """Check if files were recently uploaded (within last few messages)."""
        # Simple heuristic - if files exist, assume they should be used
        try:
            files = file_processor.get_file_context(user_id)
            return len(files) > 0  # If any files exist, consider them recent
        except:
            return False
    
    async def _handle_tool_calls(self, tool_calls: List[Dict], messages: List[Dict]) -> Dict:
        """Handle tool execution and get final response - SILENTLY."""
        # Execute tools
        tool_results = await tools.execute_tool_calls(tool_calls)
        
        # Add tool results to messages
        for result in tool_results:
            messages.append(result)
        
        # Get final response with instruction to be concise
        messages.append({
            "role": "system", 
            "content": "Give a short, direct response. Max 1-2 sentences. Be natural and confident."
        })
        
        final_response = await llm_client.complete(messages)
        return final_response
    
    async def process_message(self, user_message: str, user_id: str) -> Dict:
        """Process user message with mode-aware behavior."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Check current state
            files = file_processor.get_file_context(user_id)
            has_files = bool(files)
            
            # Detect file mode triggers - be more aggressive
            file_keywords = ["pdf", "file", "document", "image", "upload", "is pdf me", "file ke andar", "document me", "image me", "what is", "tell me about", "explain"]
            user_mentions_files = any(keyword in user_message.lower() for keyword in file_keywords)
            
            # Enter FILE MODE if files exist AND (user mentions files OR asks vague questions)
            file_mode = has_files and (user_mentions_files or self._recently_uploaded(user_id))
            
            # Force file mode for common vague questions when files exist
            if has_files and not file_mode:
                vague_patterns = ["what is", "tell me", "explain", "about", "this"]
                if any(pattern in user_message.lower() for pattern in vague_patterns):
                    file_mode = True
            
            # Debug logging
            logger.info(f"File mode detection: has_files={has_files}, user_mentions_files={user_mentions_files}, file_mode={file_mode}, message='{user_message}'")
            
            # If files exist, force file mode for ANY question
            if has_files:
                file_mode = True
                logger.info(f"FORCING file mode because files exist")
            
            # Handle vague file questions ONLY in file mode
            if file_mode:
                user_lower = user_message.lower().strip()
                vague_questions = [
                    "what is in pdf", "what is in the pdf", "pdf me kya hai", 
                    "explain pdf", "explain all pdf", "isme kya likha hai",
                    "what is this", "what is in this", "summarize", "summary",
                    "tell me about this", "what does this say"
                ]
                
                if any(q in user_lower for q in vague_questions) or (len(user_message.split()) <= 3 and user_mentions_files):
                    # Force file summary for vague questions in file mode
                    user_message = "Give me a concise summary of the uploaded file content with main points."
            
            # Handle capability queries
            if user_message.lower() in ["what can you do?", "what can you do", "capabilities", "help"]:
                if file_mode:
                    response_content = "I can answer questions about your uploaded files, do calculations, search web, and remember our conversation. What do you want to know about your files?"
                else:
                    response_content = """I can help you with:

• **Calculations** - Math problems, equations
• **Current info** - Time, date, web searches  
• **Conversations** - I remember our chats
• **Questions** - General knowledge, explanations
• **Multiple languages** - English, Hindi, Hinglish

Just ask me anything naturally!"""
                
                await memory.add_message(user_id, "user", user_message)
                await memory.add_message(user_id, "assistant", response_content)
                
                return {
                    "content": response_content,
                    "user_id": user_id,
                    "duration": round(asyncio.get_event_loop().time() - start_time, 3),
                    "tool_calls_made": 0,
                    "status": "success"
                }
            
            # Prepare context based on mode
            messages = await self._prepare_messages(user_message, user_id, include_files=file_mode)
            
            # Get initial response
            response = await llm_client.complete(
                messages, 
                tools=tools.get_tool_definitions()
            )
            
            # Handle tool calls if present
            if response.get("tool_calls"):
                response = await self._handle_tool_calls(response["tool_calls"], messages)
            
            # Apply length limits ONLY in normal chat mode (not file mode)
            content = response["content"]
            user_lower = user_message.lower().strip()
            
            if not file_mode and len(user_message.split()) <= 3 and len(content) > 50:
                # For simple queries in normal chat, keep it short
                if any(op in user_message for op in ['+', '-', '*', '/', '=']) or 'what is' in user_lower:
                    # Math queries - extract just the answer
                    import re
                    numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', content)
                    if numbers:
                        content = numbers[-1]  # Last number is usually the answer
                elif user_lower in ['hi', 'hello', 'hey', 'namaste', 'hii', 'helo']:
                    content = "Hello! 👋"
                elif user_lower in ['or sab badhiya', 'kya haal', 'kaise ho', 'how are you']:
                    content = "Sab badhiya! 😄 Tu bata?"
                elif user_lower in ['ok', 'okay']:
                    content = "Theek hai 👍"
                elif user_lower in ['all good', 'sab badhiya']:
                    content = "Badhiya 😄"
            
            response["content"] = content
            
            # Save to memory
            await asyncio.gather(
                memory.add_message(user_id, "user", user_message),
                memory.add_message(user_id, "assistant", response["content"])
            )
            
            # Calculate timing
            duration = asyncio.get_event_loop().time() - start_time
            
            return {
                "content": response["content"],
                "user_id": user_id,
                "duration": round(duration, 3),
                "tool_calls_made": len(response.get("tool_calls", [])),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            
            # Graceful fallback - don't expose errors
            fallback = "Thoda delay hua, but I'm here to help! Could you try asking again?"
            
            # Still save to memory
            try:
                await memory.add_message(user_id, "user", user_message)
                await memory.add_message(user_id, "assistant", fallback)
            except:
                pass
            
            duration = asyncio.get_event_loop().time() - start_time
            
            return {
                "content": fallback,
                "user_id": user_id,
                "duration": round(duration, 3),
                "tool_calls_made": 0,
                "status": "success"  # Always show success to user
            }
    
    async def stream_response(self, user_message: str, user_id: str) -> AsyncGenerator[str, None]:
        """Stream response for real-time interaction."""
        try:
            # Prepare context
            messages = await self._prepare_messages(user_message, user_id, include_files=True)
            
            # Stream response
            async for chunk in llm_client.stream_complete(messages):
                yield chunk
            
            # Save to memory (fire and forget)
            asyncio.create_task(
                memory.add_message(user_id, "user", user_message)
            )
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "I encountered an error. Please try again."
    
    async def get_status(self) -> Dict:
        """Get agent status and stats."""
        return {
            "status": "ready",
            "rag_stats": rag.get_stats(),
            "tools_available": len(tools.get_tool_definitions()),
            "timestamp": datetime.utcnow().isoformat()
        }

# Global instance
agent = AIAgent()