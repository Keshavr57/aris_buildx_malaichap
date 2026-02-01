"""Competition-specific configuration."""

# Competition settings - MODIFY THESE FOR YOUR PROBLEM
COMPETITION_NAME = "Hackathon Competition"
PROBLEM_DOMAIN = "General AI Assistant"
RESPONSE_STYLE = "helpful_and_fast"

# Prompt configuration
USE_COMPETITION_PROMPT = False  # Set to True to use competition_prompt.txt
SYSTEM_PROMPT_FILE = "prompts/system_prompt.txt"
COMPETITION_PROMPT_FILE = "prompts/competition_prompt.txt"

# Memory settings
ENABLE_MEMORY = True
MAX_CONVERSATION_HISTORY = 20
MEMORY_TIMEOUT_HOURS = 24

# Tool configuration
ENABLED_TOOLS = [
    "web_search",
    "calculate", 
    "get_time"
]

# Add custom tools here for your competition
CUSTOM_TOOLS = {
    # Example:
    # "domain_search": {
    #     "description": "Search domain-specific database",
    #     "enabled": True
    # }
}

# Response optimization
MAX_RESPONSE_LENGTH = 1000
PRIORITIZE_SPEED = True
ENABLE_STREAMING = True