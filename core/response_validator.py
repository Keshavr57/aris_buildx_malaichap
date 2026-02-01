"""ULTRA-STRICT response validation and enforcement."""
import re
from typing import List

class ResponseValidator:
    """ULTRA-STRICT enforcement - NO exceptions allowed."""
    
    def __init__(self):
        # BANNED phrases - therapy/advice language
        self.banned_phrases = [
            "it depends", "remember", "stay motivated", "take a moment",
            "questions to ask yourself", "consider", "you might want to",
            "it's important to", "keep in mind", "don't forget",
            "ultimately", "at the end of the day", "think about",
            "reflect on", "ask yourself", "take time to", "it's worth",
            "you may want", "consider whether", "self care", "mental health",
            "meditation", "breathe", "relax", "wellness", "balance",
            "emotional", "feelings", "therapy", "mindfulness", "peace"
        ]
        
        # BANNED health/advice words
        self.banned_health_words = [
            "meditation", "exercise", "mental health", "self care",
            "stay motivated", "take care", "mindfulness", "breathe",
            "relax", "stress", "anxiety", "wellness", "balance",
            "emotional", "feelings", "therapy", "counseling",
            "support", "journey", "growth", "healing", "peace"
        ]
        
        # Strict limits
        self.max_total_words = 80  # MUCH stricter
        self.max_bullets = 3
        self.max_questions = 0  # NO questions allowed
    
    def ultra_strict_validate(self, response: str, intent: str) -> str:
        """ULTRA-STRICT validation - force compliance."""
        
        # Step 1: Check for banned content - REJECT if found
        if self._has_banned_content(response):
            return self._get_emergency_fallback(intent)
        
        # Step 2: Remove any questions
        response = self._remove_all_questions(response)
        
        # Step 3: Enforce word limits HARD
        response = self._hard_word_limit(response)
        
        # Step 4: Remove excess bullets
        response = self._limit_bullets_strict(response)
        
        # Step 5: FORCE "Do this today" ending
        response = self._force_action_ending(response, intent)
        
        # Step 6: Final structure check - use fallback if invalid
        if not self._is_structurally_valid(response, intent):
            return self._get_emergency_fallback(intent)
        
        return response.strip()
    
    def _has_banned_content(self, text: str) -> bool:
        """Check for ANY banned content."""
        text_lower = text.lower()
        
        # Check banned phrases
        for phrase in self.banned_phrases:
            if phrase in text_lower:
                return True
        
        # Check banned health words
        for word in self.banned_health_words:
            if word in text_lower:
                return True
        
        return False
    
    def _remove_all_questions(self, text: str) -> str:
        """Remove ALL questions - none allowed."""
        sentences = re.split(r'[.!?]+', text)
        filtered = []
        
        for sentence in sentences:
            if '?' not in sentence:
                filtered.append(sentence.strip())
        
        return '. '.join(s for s in filtered if s)
    
    def _hard_word_limit(self, text: str) -> str:
        """HARD word limit - cut off ruthlessly."""
        words = text.split()
        if len(words) > self.max_total_words:
            # Keep first N words, ensure "Do this today" at end
            truncated = ' '.join(words[:self.max_total_words-5])
            truncated += "\n\n**Do this today:** Complete first task."
            return truncated
        return text
    
    def _limit_bullets_strict(self, text: str) -> str:
        """Strict bullet limit."""
        lines = text.split('\n')
        bullet_count = 0
        filtered_lines = []
        
        for line in lines:
            if re.match(r'^\s*[•\-\*]\s+', line) or re.match(r'^\s*\d+\.\s+', line):
                bullet_count += 1
                if bullet_count <= self.max_bullets:
                    filtered_lines.append(line)
            else:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def _force_action_ending(self, text: str, intent: str) -> str:
        """FORCE "Do this today" - NO exceptions."""
        if "do this today" not in text.lower():
            if intent == "DECIDE":
                text += "\n\n**Do this today:** Choose recommended option immediately."
            elif intent == "PLAN":
                text += "\n\n**Do this today:** Start step 1 now."
            elif intent == "ORGANIZE":
                text += "\n\n**Do this today:** Focus on highest priority."
            else:  # CHAT
                text += "\n\n**Do this today:** Be specific about what you need."
        
        return text
    
    def _is_structurally_valid(self, text: str, intent: str) -> bool:
        """Check structure is valid."""
        text_lower = text.lower()
        
        # Must have "Do this today"
        if "do this today" not in text_lower:
            return False
        
        # Intent-specific checks
        if intent == "DECIDE":
            return "recommendation" in text_lower and "decision" in text_lower
        elif intent == "PLAN":
            return "goal" in text_lower and ("step" in text_lower or "1." in text)
        elif intent == "ORGANIZE":
            return ("priority" in text_lower or "high" in text_lower) and "task" in text_lower
        
        return True
    
    def _get_emergency_fallback(self, intent: str) -> str:
        """Emergency fallback responses - guaranteed clean."""
        fallbacks = {
            "DECIDE": """**Decision:** Need specific options

**Recommendation:** Provide clear choices

**Reason:**
• Cannot decide without alternatives
• Need specific options

**Do this today:** List exact options to choose between.""",
            
            "PLAN": """**Goal:** Unclear objective

**Steps:**
1. Define specific goal
2. Set deadline
3. List requirements
4. Create timeline
5. Start first task

**Do this today:** State exactly what you want to achieve.""",
            
            "ORGANIZE": """**Tasks:**
• Task A
• Task B
• Task C

**Priority:**
• High: Most urgent deadline
• Medium: Important but flexible
• Low: Optional items

**Do this today:** Focus on highest priority task.""",
            
            "CHAT": "Be specific about what you need."
        }
        
        return fallbacks.get(intent, fallbacks["CHAT"])

# Global instance
response_validator = ResponseValidator()