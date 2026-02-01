"""HARD enforcement - bypass LLM when needed."""
import re
from typing import Optional

class HardEnforcer:
    """Hard-coded responses and content blocking."""
    
    def __init__(self):
        # BANNED words that make responses sound like therapy/advice
        self.banned_words = [
            "meditation", "exercise", "mental health", "self care", 
            "stay motivated", "take care", "mindfulness", "breathe",
            "relax", "stress", "anxiety", "wellness", "balance",
            "emotional", "feelings", "therapy", "counseling",
            "support", "journey", "growth", "healing", "peace"
        ]
        
        # Student context to inject
        self.student_context = """Assume user is a college student. Deadlines matter. Time is limited. Practical outcomes > theory."""
    
    def handle_chat_mode(self, user_input: str) -> Optional[str]:
        """HARD override for CHAT mode - NO LLM needed."""
        text = user_input.lower().strip()
        
        # Greeting responses
        if any(word in text for word in ["hi", "hello", "hey", "hii"]):
            return "Hi 👋 Need help deciding, planning, or organizing something?"
        
        if any(word in text for word in ["ok", "okay", "alright", "thanks", "thank you"]):
            return "Great! What else can I help you decide, plan, or organize?"
        
        if "what can you do" in text or "capabilities" in text or "help" in text:
            return """I'm your AI Thinking Assistant. I help you:

• **Decide** - Choose between options with clear recommendations
• **Plan** - Break goals into actionable steps  
• **Organize** - Prioritize tasks and manage time

**Do this today:** Tell me what you need help with."""
        
        # More specific responses instead of just "Batao"
        if any(word in text for word in ["unclear", "confused", "don't know", "not sure"]):
            return "What specifically do you need help with - deciding between options, planning something, or organizing tasks?"
        
        # Default - be more helpful
        return "What would you like help with today - deciding, planning, or organizing?"
    
    def has_banned_content(self, response: str) -> bool:
        """Check if response contains banned advice/therapy words."""
        response_lower = response.lower()
        return any(word in response_lower for word in self.banned_words)
    
    def get_student_context(self) -> str:
        """Get student context to inject."""
        return self.student_context
    
    def fix_organize_response(self, user_input: str) -> str:
        """Hard-coded ORGANIZE response - no advice allowed."""
        # Extract tasks from input (simple keyword matching)
        tasks = []
        if "college" in user_input.lower():
            tasks.append("College work")
        if "side hustle" in user_input.lower() or "business" in user_input.lower():
            tasks.append("Side hustle")
        if "family" in user_input.lower():
            tasks.append("Family responsibilities")
        if "work" in user_input.lower() and "side" not in user_input.lower():
            tasks.append("Work tasks")
        if "gym" in user_input.lower() or "fitness" in user_input.lower():
            tasks.append("Gym/fitness")
        if "health" in user_input.lower():
            tasks.append("Health appointments")
        
        # Default tasks if none detected
        if not tasks:
            tasks = ["Task 1", "Task 2", "Task 3"]
        
        # Build response with strict priority logic
        high_task = tasks[0] if tasks else "Most urgent task"
        medium_task = tasks[1] if len(tasks) > 1 else "Secondary task"
        low_task = tasks[2] if len(tasks) > 2 else "Optional task"
        
        return f"""**Tasks:**
• {high_task}
• {medium_task}
• {low_task}

**Priority:**
• High: {high_task}
• Medium: {medium_task}
• Low: {low_task}

**Do this today:** Focus on {high_task}"""
    
    def fix_decide_response(self, response: str) -> str:
        """Remove Options section from DECIDE responses."""
        # Remove "Options:" section
        lines = response.split('\n')
        filtered_lines = []
        skip_options = False
        
        for line in lines:
            if line.strip().startswith("**Options:**"):
                skip_options = True
                continue
            elif line.strip().startswith("**") and skip_options:
                skip_options = False
                filtered_lines.append(line)
            elif not skip_options:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)

# Global instance
hard_enforcer = HardEnforcer()