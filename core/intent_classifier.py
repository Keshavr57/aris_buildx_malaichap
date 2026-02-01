"""Strict rule-based intent classification."""
import re
from typing import Literal

IntentType = Literal["DECIDE", "PLAN", "ORGANIZE", "CHAT"]

class IntentClassifier:
    """Strict rule-based intent classifier - NO LLM fallback."""
    
    def __init__(self):
        # DECIDE patterns - choosing between options
        self.decide_patterns = [
            r"should\s+i",
            r"which\s+is\s+better",
            r"which\s+should\s+i",
            r"confused\s+between",
            r"help\s+me\s+choose",
            r"decide\s+between",
            r"what\s+should\s+i\s+pick",
            r"recommend",
            r"better\s+option",
            r"vs\s+",
            r"or\s+.*\?",
            r"pick\s+between",
            r"choose\s+between"
        ]
        
        # PLAN patterns - achieving goals, building things
        self.plan_patterns = [
            r"i\s+want\s+to\s+achieve",
            r"i\s+want\s+to\s+build",
            r"i\s+want\s+to\s+create",
            r"i\s+want\s+to\s+improve",
            r"i\s+want\s+to\s+prepare",
            r"help\s+me\s+plan",
            r"i\s+need\s+a\s+roadmap",
            r"how\s+do\s+i\s+prepare",
            r"how\s+do\s+i\s+build",
            r"how\s+do\s+i\s+create",
            r"how\s+do\s+i\s+improve",
            r"step\s+by\s+step",
            r"roadmap",
            r"strategy\s+for",
            r"approach\s+to",
            r"how\s+to\s+get",
            r"build\s+a\s+startup",
            r"start\s+a\s+business",
            r"learn\s+.*\s+plan",
            r"prepare\s+for\s+exams",
            r"improve.*resume",
            r"get\s+ready\s+for",
            r"study\s+plan",
            r"preparation\s+for"
        ]
        
        # ORGANIZE patterns - managing tasks, time, priorities
        self.organize_patterns = [
            r"i\s+have\s+too\s+many",
            r"help\s+me\s+manage",
            r"i'm\s+overwhelmed",
            r"organize\s+my\s+tasks",
            r"prioritize",
            r"schedule",
            r"time\s+management",
            r"juggling",
            r"balance",
            r"work.*gym.*family",
            r"manage.*time",
            r"too\s+much\s+to\s+do",
            r"organize\s+my",
            r"manage\s+my",
            r"overwhelmed\s+with",
            r"too\s+many\s+tasks",
            r"help.*prioritize",
            r"college.*side.*hustle",
            r"college.*family.*work",
            r"multiple\s+responsibilities"
        ]
    
    def classify(self, message: str) -> IntentType:
        """Classify using ONLY rule-based logic - no LLM."""
        message_lower = message.lower().strip()
        
        # Count pattern matches
        decide_score = sum(1 for pattern in self.decide_patterns if re.search(pattern, message_lower))
        plan_score = sum(1 for pattern in self.plan_patterns if re.search(pattern, message_lower))
        organize_score = sum(1 for pattern in self.organize_patterns if re.search(pattern, message_lower))
        
        # Return highest scoring intent
        if decide_score > 0 and decide_score >= plan_score and decide_score >= organize_score:
            return "DECIDE"
        elif plan_score > 0 and plan_score >= organize_score:
            return "PLAN"
        elif organize_score > 0:
            return "ORGANIZE"
        else:
            # Better CHAT detection - check for common chat patterns
            chat_patterns = [
                r"^hi$", r"^hello$", r"^hey$", r"^what.*do$", r"^how.*you$",
                r"^ok$", r"^okay$", r"^thanks$", r"^thank you$"
            ]
            
            # If it's clearly a chat message, return CHAT
            if any(re.search(pattern, message_lower) for pattern in chat_patterns):
                return "CHAT"
            
            # If message contains decision/planning/organizing keywords but didn't match patterns,
            # try to infer intent from keywords
            if any(word in message_lower for word in ["choose", "pick", "better", "decide", "which", "should i", "vs", "or"]):
                return "DECIDE"
            elif any(word in message_lower for word in ["plan", "how to", "steps", "build", "create", "achieve", "improve", "prepare", "study", "ready"]):
                return "PLAN"
            elif any(word in message_lower for word in ["organize", "manage", "priority", "tasks", "schedule", "time management"]):
                return "ORGANIZE"
            
            return "CHAT"

# Global instance
intent_classifier = IntentClassifier()