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
    
    async def _prepare_messages(self, user_message: str, user_id: str, include_files: bool = False) -> List[Dict]:
        """Prepare message context with memory and RAG for thinking assistant."""
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
        """Process user message with thinking assistant behavior."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Handle capability queries
            if user_message.lower() in ["what can you do?", "what can you do", "capabilities", "help"]:
                response_content = """I'm an AI Thinking Assistant. I help you:

• **Decide** - Choose between options with pros/cons
• **Plan** - Break goals into actionable steps  
• **Organize** - Structure tasks and priorities
• **Chat** - Brief support for the above

What would you like help thinking through?"""
                
                await memory.add_message(user_id, "user", user_message)
                await memory.add_message(user_id, "assistant", response_content)
                
                return {
                    "content": response_content,
                    "user_id": user_id,
                    "duration": round(asyncio.get_event_loop().time() - start_time, 3),
                    "tool_calls_made": 0,
                    "status": "success"
                }
            
            # Prepare context for thinking assistant
            messages = await self._prepare_messages(user_message, user_id, include_files=False)
            
            # Get initial response
            response = await llm_client.complete(
                messages, 
                tools=tools.get_tool_definitions()
            )
            
            # Handle tool calls if present
            if response.get("tool_calls"):
                response = await self._handle_tool_calls(response["tool_calls"], messages)
            
            # Keep responses structured and concise for thinking assistant
            content = response["content"]
            
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
            
            # Graceful fallback
            fallback = "Let me help you think through this. Could you clarify what you need help deciding, planning, or organizing?"
            
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
                "status": "success"
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