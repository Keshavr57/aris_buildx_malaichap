"""Tool system with async execution and error handling."""
import asyncio
import json
import logging
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
import httpx

# Import competition tools
try:
    from tools.custom_tools import competition_tools
    CUSTOM_TOOLS_AVAILABLE = True
except ImportError:
    CUSTOM_TOOLS_AVAILABLE = False

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Dict] = {}
        self.functions: Dict[str, Callable] = {}
        self._register_default_tools()
        if CUSTOM_TOOLS_AVAILABLE:
            self._register_custom_tools()
    
    def register_tool(self, name: str, func: Callable, description: str, parameters: Dict):
        """Register a new tool."""
        self.tools[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        }
        self.functions[name] = func
        logger.info(f"Tool registered: {name}")
    
    def _register_custom_tools(self):
        """Register competition-specific tools."""
        if not CUSTOM_TOOLS_AVAILABLE:
            return
            
        # Register custom tools
        custom_tool_defs = competition_tools.get_tool_definitions()
        for name, tool_def in custom_tool_defs.items():
            func = getattr(competition_tools, name, None)
            if func:
                self.tools[name] = tool_def
                self.functions[name] = func
                logger.info(f"Custom tool registered: {name}")
    
    def _register_default_tools(self):
        """Register default hackathon-useful tools."""
        
        # Web search tool
        self.register_tool(
            "web_search",
            self._web_search,
            "Search the web for current information",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        )
        
        # Calculator tool
        self.register_tool(
            "calculate",
            self._calculate,
            "Perform mathematical calculations",
            {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Mathematical expression to evaluate"}
                },
                "required": ["expression"]
            }
        )
        
        # Time tool
        self.register_tool(
            "get_time",
            self._get_time,
            "Get current date and time",
            {
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    
    async def _web_search(self, query: str) -> str:
        """Simple web search (placeholder - integrate with real API)."""
        try:
            # Placeholder implementation
            await asyncio.sleep(0.1)  # Simulate API call
            return f"Search results for '{query}': [This is a placeholder. Integrate with real search API for hackathon.]"
        except Exception as e:
            return f"Search failed: {e}"
    
    async def _calculate(self, expression: str) -> str:
        """Safe calculator."""
        try:
            # Basic safety check
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return "Invalid characters in expression"
            
            result = eval(expression)
            return str(result)
        except Exception as e:
            return f"Calculation error: {e}"
    
    async def _get_time(self) -> str:
        """Get current time."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    async def execute_tool(self, name: str, arguments: Dict) -> str:
        """Execute a tool with error handling."""
        if name not in self.functions:
            return f"Tool '{name}' not found"
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self.functions[name](**arguments),
                timeout=10.0  # 10 second timeout
            )
            return str(result)
            
        except asyncio.TimeoutError:
            return f"Tool '{name}' timed out"
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"Tool '{name}' failed: {str(e)}"
    
    def get_tool_definitions(self) -> List[Dict]:
        """Get all tool definitions for LLM."""
        return list(self.tools.values())
    
    async def execute_tool_calls(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute multiple tool calls concurrently."""
        if not tool_calls:
            return []
        
        # Execute all tools concurrently
        tasks = []
        for tool_call in tool_calls:
            func_name = tool_call["function"]["name"]
            try:
                arguments = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError:
                arguments = {}
            
            task = self.execute_tool(func_name, arguments)
            tasks.append((tool_call["id"], task))
        
        # Wait for all results
        results = []
        for tool_id, task in tasks:
            try:
                result = await task
                results.append({
                    "tool_call_id": tool_id,
                    "role": "tool",
                    "content": result
                })
            except Exception as e:
                results.append({
                    "tool_call_id": tool_id,
                    "role": "tool",
                    "content": f"Execution failed: {e}"
                })
        
        return results

# Global instance
tools = ToolRegistry()