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
from .intent_classifier import intent_classifier
from .prompt_templates import response_templates
from .response_validator import response_validator
from .hard_enforcer import hard_enforcer

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
    
    async def _prepare_messages(self, user_message: str, user_id: str, intent: str) -> List[Dict]:
        """Legacy method - redirects to strict version."""
        return await self._prepare_messages_strict(user_message, user_id, intent)

    

    async def process_message(self, user_message: str, user_id: str) -> Dict:
        """Process user message with ULTRA-STRICT enforcement."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # STEP 1: HARD CHAT MODE OVERRIDE - NO LLM
            intent = intent_classifier.classify(user_message)
            
            if intent == "CHAT":
                chat_response = hard_enforcer.handle_chat_mode(user_message)
                
                await memory.add_message(user_id, "user", user_message)
                await memory.add_message(user_id, "assistant", chat_response)
                
                return {
                    "content": chat_response,
                    "user_id": user_id,
                    "duration": round(asyncio.get_event_loop().time() - start_time, 3),
                    "tool_calls_made": 0,
                    "status": "success",
                    "intent": "CHAT"
                }
            
            # STEP 2: ORGANIZE MODE - HARD OVERRIDE for health/stress mentions
            if intent == "ORGANIZE" or any(word in user_message.lower() for word in ["health", "stress", "overwhelmed", "anxiety", "college", "side hustle"]):
                # Force ORGANIZE intent if health/stress mentioned
                if intent == "CHAT" and any(word in user_message.lower() for word in ["college", "side hustle", "family work", "responsibilities"]):
                    intent = "ORGANIZE"
                
                organize_response = hard_enforcer.fix_organize_response(user_message)
                
                await memory.add_message(user_id, "user", user_message)
                await memory.add_message(user_id, "assistant", organize_response)
                
                return {
                    "content": organize_response,
                    "user_id": user_id,
                    "duration": round(asyncio.get_event_loop().time() - start_time, 3),
                    "tool_calls_made": 0,
                    "status": "success",
                    "intent": "ORGANIZE"
                }
            
            # STEP 3: For DECIDE/PLAN - use LLM with STRICT enforcement
            messages = await self._prepare_messages_strict(user_message, user_id, intent)
            
            # Get response (no tools to keep it focused)
            response = await llm_client.complete(messages)
            
            # STEP 4: ULTRA-STRICT validation
            if response.get("content"):
                # Check for banned content first
                if hard_enforcer.has_banned_content(response["content"]):
                    response["content"] = self._get_clean_fallback(intent, user_message)
                else:
                    response["content"] = response_validator.ultra_strict_validate(
                        response["content"], intent
                    )
                    
                    # Fix DECIDE responses (remove Options section)
                    if intent == "DECIDE":
                        response["content"] = hard_enforcer.fix_decide_response(response["content"])
            
            # STEP 5: Final safety check
            if hard_enforcer.has_banned_content(response.get("content", "")):
                response["content"] = self._get_clean_fallback(intent, user_message)
            
            # Save to memory
            await asyncio.gather(
                memory.add_message(user_id, "user", user_message),
                memory.add_message(user_id, "assistant", response["content"])
            )
            
            duration = asyncio.get_event_loop().time() - start_time
            
            return {
                "content": response["content"],
                "user_id": user_id,
                "duration": round(duration, 3),
                "tool_calls_made": 0,
                "status": "success",
                "intent": intent
            }
            
        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            
            # Clean fallback
            intent = intent_classifier.classify(user_message)
            fallback = self._get_clean_fallback(intent, user_message)
            
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
                "status": "success",
                "intent": intent
            }
    
    async def _prepare_messages_strict(self, user_message: str, user_id: str, intent: str) -> List[Dict]:
        """Prepare messages with ULTRA-STRICT context."""
        # Initialize Redis connections if needed
        if not llm_client.redis_client:
            await llm_client._init_redis()
        if not memory.redis_client:
            await memory._init_redis()

        messages = []
        
        # INJECT student context HARD
        student_context = hard_enforcer.get_student_context()
        system_prompt = response_templates.get_system_prompt(intent)
        
        messages.append({
            "role": "system",
            "content": f"{student_context}\n\n{system_prompt}"
        })
        
        # NO conversation history to prevent bloat
        # NO RAG context to prevent advice injection
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    def _get_clean_fallback(self, intent: str, user_input: str) -> str:
        """Get guaranteed clean fallback."""
        if intent == "DECIDE":
            return """**Decision:** Need specific options

**Recommendation:** Provide clear choices

**Reason:**
• Cannot decide without alternatives
• Need exact options

**Do this today:** List the options you're choosing between."""
        
        elif intent == "PLAN":
            return """**Goal:** Unclear objective

**Steps:**
1. Define specific goal
2. Set deadline
3. List requirements
4. Create timeline
5. Start first task

**Do this today:** State exactly what you want to achieve."""
        
        elif intent == "ORGANIZE":
            return hard_enforcer.fix_organize_response(user_input)
        
        else:  # CHAT
            return "Batao."
    
    async def stream_response(self, user_message: str, user_id: str) -> AsyncGenerator[str, None]:
        """Stream response with ULTRA-STRICT validation."""
        try:
            # HARD CHAT MODE OVERRIDE
            intent = intent_classifier.classify(user_message)
            
            if intent == "CHAT":
                chat_response = hard_enforcer.handle_chat_mode(user_message)
                yield chat_response
                return
            
            # For other intents, use strict preparation
            messages = await self._prepare_messages_strict(user_message, user_id, intent)
            
            # Stream response
            response_content = ""
            async for chunk in llm_client.stream_complete(messages):
                response_content += chunk
                yield chunk
            
            # ULTRA-STRICT validation of streamed response
            if response_content:
                if hard_enforcer.has_banned_content(response_content):
                    yield f"\n\n[Clean response]\n{self._get_clean_fallback(intent, user_message)}"
                else:
                    fixed_content = response_validator.ultra_strict_validate(response_content, intent)
                    if fixed_content != response_content:
                        yield f"\n\n[Enforced structure]\n{fixed_content}"
            
            # Save to memory
            asyncio.create_task(
                memory.add_message(user_id, "user", user_message)
            )
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "Error. Be specific about what you need."
    
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