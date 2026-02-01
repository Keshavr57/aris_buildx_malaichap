"""Fixed response templates - STRICT format only."""

class ResponseTemplates:
    """Hard-coded templates that LLM must fill exactly."""
    
    @staticmethod
    def get_decide_template() -> str:
        """DECIDE template - NO Options section."""
        return """**Decision:** [state decision in 5 words max]

**Recommendation:** [Pick EXACTLY ONE option - no "both" or "depends"]

**Reason:**
• [Reason 1 - max 8 words]
• [Reason 2 - max 8 words]

**Do this today:** [ONE specific action - max 12 words]"""

    @staticmethod
    def get_plan_template() -> str:
        """PLAN template - max 5 steps, student context."""
        return """**Goal:** [restate goal in 5 words max]

**Steps:**
1. [Step 1 - max 8 words]
2. [Step 2 - max 8 words]
3. [Step 3 - max 8 words]
4. [Step 4 - max 8 words]
5. [Step 5 - max 8 words]

**Do this today:** [First concrete action - max 12 words]"""

    @staticmethod
    def get_organize_template() -> str:
        """ORGANIZE template - priorities only, NO advice."""
        return """**Tasks:**
• [Task 1]
• [Task 2]
• [Task 3]

**Priority:**
• High: [Deadline-driven task]
• Medium: [Important but flexible]
• Low: [Optional/deferrable]

**Do this today:** [ONE highest priority task - max 12 words]"""

    @staticmethod
    def get_system_prompt(intent: str) -> str:
        """Get system prompt for specific intent."""
        student_context = "User is a college student. Deadlines matter. Time limited. Practical outcomes only."
        base = f"{student_context}\n\nBe decisive. Pick ONE option. No advice. No motivation. No health tips."
        
        if intent == "DECIDE":
            template = ResponseTemplates.get_decide_template()
            return f"{base}\n\nFill this template EXACTLY:\n{template}\n\nMUST pick ONE recommendation. NO neutral answers. NO Options section."
            
        elif intent == "PLAN":
            template = ResponseTemplates.get_plan_template()
            return f"{base}\n\nFill this template EXACTLY:\n{template}\n\nMax 5 steps. Be specific. No generic advice."
            
        elif intent == "ORGANIZE":
            template = ResponseTemplates.get_organize_template()
            return f"{base}\n\nFill this template EXACTLY:\n{template}\n\nPriorities only. NO health advice. NO self-care. NO meditation."
            
        else:  # CHAT - should not reach here
            return f"{base}\n\nOne sentence only. No planning. No advice."

# Global instance
response_templates = ResponseTemplates()