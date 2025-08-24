import openai
import json
import time
import random
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from config import settings
from validators import validate_bullet

class AIClient:
    """AI client wrapper with caching, retries, and JSON schema enforcement."""
    
    def __init__(self):
        """Initialize the AI client with OpenAI configuration."""
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.AI_TIMEOUT_SECONDS
        )
        
        # Simple in-memory cache with TTL
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 600  # 10 minutes in seconds
        
        # Retry configuration
        self.max_retries = 2
        self.base_delay = 1.0  # Base delay in seconds
    
    def _get_cache_key(self, method: str, **kwargs) -> str:
        """Generate a cache key for the given method and parameters."""
        # Create a deterministic key from the method and sorted kwargs
        key_parts = [method]
        for k, v in sorted(kwargs.items()):
            if isinstance(v, (str, int, float, bool)):
                key_parts.append(f"{k}:{v}")
        return "|".join(key_parts)
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if a cache entry is still valid."""
        if 'timestamp' not in cache_entry:
            return False
        
        age = time.time() - cache_entry['timestamp']
        return age < self.cache_ttl
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Retrieve a value from cache if it exists and is valid."""
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if self._is_cache_valid(cache_entry):
                return cache_entry['data']
            else:
                # Remove expired entry
                del self.cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, data: Any):
        """Store data in cache with timestamp."""
        self.cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def _exponential_backoff_with_jitter(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.base_delay * (2 ** attempt)
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter
    
    def _adjust_item_counts(self, bullets: list, skills: list, bullet_min: int = 3, bullet_max: int = 5) -> tuple:
        """Adjust bullet points and skills to meet count requirements."""
        # Adjust bullet points based on dynamic range
        if len(bullets) < bullet_min:
            # Pad with generic bullets if we have too few
            generic_bullets = [
                "Demonstrated strong work ethic and commitment to achieving goals.",
                "Successfully completed assigned tasks within established deadlines.",
                "Maintained high quality standards throughout the project duration.",
                "Collaborated effectively with team members to achieve objectives.",
                "Adapted quickly to changing requirements and priorities."
            ]
            while len(bullets) < bullet_min:
                bullets.append(generic_bullets[len(bullets) % len(generic_bullets)])
        elif len(bullets) > bullet_max:
            # Truncate if we have too many
            bullets = bullets[:bullet_max]
        
        # Adjust skills
        if len(skills) < 5:
            # Pad with generic skills if we have too few
            generic_skills = ["Problem Solving", "Communication", "Teamwork", "Adaptability", "Time Management"]
            for skill in generic_skills:
                if len(skills) >= 5:
                    break
                if skill not in skills:
                    skills.append(skill)
        elif len(skills) > 7:
            # Truncate if we have too many
            skills = skills[:7]
        
        return bullets, skills
    
    def _make_request_with_retries(self, method: str, **kwargs) -> Any:
        """Make an OpenAI API request with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if method == "generate_initial":
                    return self._generate_initial_request(**kwargs)
                elif method == "refine_bullets":
                    return self._refine_bullets_request(**kwargs)
                else:
                    raise ValueError(f"Unknown method: {method}")
                    
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = self._exponential_backoff_with_jitter(attempt)
                    time.sleep(delay)
                    continue
                else:
                    break
        
        # If we get here, all retries failed
        raise last_exception or Exception("Unknown error occurred")
    
    def _generate_initial_request(self, experience_type: str, experience_text: str) -> Dict[str, Any]:
        """Make the actual OpenAI API call for initial generation."""
        # Analyze experience length and detail level
        word_count = len(experience_text.split())
        is_detailed = word_count > 150 or len(experience_text) > 800  # More than 150 words or 800 characters
        
        # Determine bullet point range based on content richness
        bullet_range = "5-7" if is_detailed else "3-5"
        bullet_min = 5 if is_detailed else 3
        bullet_max = 7 if is_detailed else 5
        
        prompt = f"""
You are a professional resume strategist and AI assistant. The user will describe one {experience_type} experience. Your job is to:

CRITICAL LANGUAGE REQUIREMENT - READ THIS FIRST:
You MUST respond in EXACTLY the same language as the user's experience description.
- If the user writes in English, respond in English
- If the user writes in Spanish, respond in Spanish  
- If the user writes in French, respond in French
- If the user writes in Korean, respond in Korean
- If the user writes in any other language, respond in that same language

DO NOT switch languages. DO NOT translate. Use the EXACT same language as the input.
This applies to ALL outputs: title, bullet points, skills, and follow-up questions.

1. Generate a short, smart title for this experience (e.g. "Community Volunteer", "Freelance Designer", "Family Caregiver") in the user's language.

2. Write {bullet_range} resume bullet points (minimum {bullet_min}, maximum {bullet_max}) using this ideal structure:
- What was done
- How it was done
- What result or achievement was gained (preferably with measurable data or impact)
- How long it took (duration)

In your bullet points:
- Bold any key metrics or quantifiable results (e.g. **20%**, **$500**, **2 months**)
- Start each bullet with a strong verb (e.g. Led, Created, Designed, Improved)

IMPORTANT: You MUST generate EXACTLY {bullet_range} bullet points, no more, no less.

3. Extract EXACTLY 5-7 relevant skills (minimum 5, maximum 7) that the person likely used in this experience. Include both hard and soft skills.

IMPORTANT: You MUST generate EXACTLY 5-7 skills, no more, no less.

4. Ask 3 targeted follow-up questions that are PURELY based on the user's entered experience description, NOT based on the bullet points you just generated. These questions should aim to:
- Clarify details that are mentioned but unclear in their original experience (e.g. "You mentioned helping people - how many people were impacted?")
- Add specific metrics or measurements from what they described (e.g. "You mentioned saving time - how much time was saved?")
- Identify time duration that was mentioned but not specific (e.g. "You mentioned this took a while - how long did it take?")

CRITICAL: Base your follow-up questions ONLY on what the user actually wrote in their experience description. Do NOT reference or ask about the bullet points you generated in step 2.

Your follow-up questions should be short, focused, and framed to get measurable or time-based answers from their original experience description.

Output format:

Experience Title:
[one-line title]

Resume Bullet Points:
...
...
...

Skills:
...
...
...

Follow-Up Questions:
1. ...
2. ...
3. ...

FINAL REMINDER: Use the EXACT same language as the user's input. DO NOT translate or switch languages.
"""

        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": experience_text}
            ],
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        
        # Parse the response into structured format
        try:
            title_part = content.split("Experience Title:")[1].split("Resume Bullet Points:")[0].strip()
            bullets_part = content.split("Resume Bullet Points:")[1].split("Skills:")[0].strip()
            skills_part = content.split("Skills:")[1].split("Follow-Up Questions:")[0].strip()
            questions_part = content.split("Follow-Up Questions:")[1].strip().split("\n")
            
            # Parse bullets (remove the "- " prefix and split by lines)
            bullets = [line.strip().lstrip('- ').strip() for line in bullets_part.split('\n') if line.strip()]
            
            # Parse skills (remove the "- " prefix and split by lines)
            skills = [line.strip().lstrip('- ').strip() for line in skills_part.split('\n') if line.strip()]
            
            questions = [q.strip() for q in questions_part if q.strip()]
            
            # Adjust item counts to meet requirements
            bullets, skills = self._adjust_item_counts(bullets, skills, bullet_min, bullet_max)
            
            return {
                'title': title_part,
                'bullet_points': bullets,
                'skills': skills,
                'questions': questions
            }
        except (IndexError, KeyError) as e:
            raise Exception(f"Failed to parse AI response: {e}")
    
    def _refine_bullets_request(self, experience_text: str, answers: list) -> Dict[str, Any]:
        """Make the actual OpenAI API call for bullet refinement."""
        # Analyze experience length and detail level
        word_count = len(experience_text.split())
        is_detailed = word_count > 150 or len(experience_text) > 800  # More than 150 words or 800 characters
        
        # Determine bullet point range based on content richness
        bullet_range = "5-7" if is_detailed else "3-5"
        bullet_min = 5 if is_detailed else 3
        bullet_max = 7 if is_detailed else 5
        
        final_prompt = f"""
You are a resume builder AI. The user shared their experience and answered 3 follow-up questions that were based on their original experience description.
Now update and improve the resume bullet points using the combined information from their original experience and their follow-up answers.

CRITICAL LANGUAGE REQUIREMENT - READ THIS FIRST:
You MUST respond in EXACTLY the same language as the user's experience description.
- If the user writes in English, respond in English
- If the user writes in Spanish, respond in Spanish  
- If the user writes in French, respond in French
- If the user writes in Korean, respond in Korean
- If the user writes in any other language, respond in that same language

DO NOT switch languages. DO NOT translate. Use the EXACT same language as the input.
This applies to ALL outputs: bullet points, skills, and suggestions.

Original experience description:
{experience_text}

Follow-up answers (based on their original experience):
1. {answers[0]}
2. {answers[1]}
3. {answers[2]}

Please output the updated content in this exact format:

Final Bullet Points:
- [First improved bullet point with specific metrics and impact from their original experience + follow-up answers]
- [Second improved bullet point with specific metrics and impact from their original experience + follow-up answers]
- [Third improved bullet point with specific metrics and impact from their original experience + follow-up answers]
- [Fourth improved bullet point with specific metrics and impact from their original experience + follow-up answers] (optional)
- [Fifth improved bullet point with specific metrics and impact from their original experience + follow-up answers] (optional)

IMPORTANT: You MUST generate EXACTLY {bullet_range} bullet points (minimum {bullet_min}, maximum {bullet_max}).

Updated Skills:
- [Skill 1]
- [Skill 2]
- [Skill 3]
- [Skill 4]
- [Skill 5]
- [Skill 6] 
- [Skill 7] 

IMPORTANT: You MUST generate EXACTLY 5-7 skills (minimum 5, maximum 7).

Suggestions:
[3-5 specific suggestions for further improvement, focusing on metrics, timeframes, or impact that could be added to their original experience description]

IMPORTANT: Each bullet point must be 150 characters or less for optimal resume formatting.

FINAL REMINDER: Use the EXACT same language as the user's input. DO NOT translate or switch languages.
"""

        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "system", "content": final_prompt}],
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        
        # Parse the response into structured format
        try:
            bullets_part = content.split("Final Bullet Points:")[1].split("Updated Skills:")[0].strip()
            skills_part = content.split("Updated Skills:")[1].split("Suggestions:")[0].strip()
            suggestions_part = content.split("Suggestions:")[1].strip()
            
            # Parse bullets (remove the "- " prefix and split by lines)
            bullets = [line.strip().lstrip('- ').strip() for line in bullets_part.split('\n') if line.strip()]
            
            # Parse skills (remove the "- " prefix and split by lines)
            skills = [line.strip().lstrip('- ').strip() for line in skills_part.split('\n') if line.strip()]
            
            # Adjust item counts to meet requirements
            bullets, skills = self._adjust_item_counts(bullets, skills, bullet_min, bullet_max)
            
            # Validate and truncate bullets to 150 characters
            validated_bullets = []
            for bullet in bullets:
                validated_bullet, _ = validate_bullet(bullet)
                if validated_bullet:
                    validated_bullets.append(validated_bullet)
            
            return {
                'final_bullets': validated_bullets,
                'final_skills': skills,
                'suggestions': suggestions_part
            }
        except (IndexError, KeyError) as e:
            # Fallback: return the raw content as bullets
            return {
                'final_bullets': [content],
                'final_skills': [],
                'suggestions': "Consider adding specific metrics and timeframes to make your experience more impactful."
            }
    
    def generate_initial(self, experience_type: str, experience_text: str) -> Dict[str, Any]:
        """
        Generate initial resume content from experience description.
        
        Args:
            experience_type (str): Type of experience (professional, personal, etc.)
            experience_text (str): User's experience description
            
        Returns:
            Dict containing title, bullet_points, skills, and questions
        """
        cache_key = self._get_cache_key("generate_initial", 
                                      experience_type=experience_type, 
                                      experience_text=experience_text)
        
        # Check cache first
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        # Make API call with retries
        result = self._make_request_with_retries("generate_initial", 
                                               experience_type=experience_type, 
                                               experience_text=experience_text)
        
        # Cache the result
        self._set_cache(cache_key, result)
        
        return result
    
    def refine_bullets(self, experience_text: str, answers: list) -> Dict[str, Any]:
        """
        Refine resume bullet points based on follow-up answers.
        
        Args:
            experience_text (str): Original experience description
            answers (list): List of follow-up answers
            
        Returns:
            Dict containing final_bullets, final_skills, and suggestions
        """
        cache_key = self._get_cache_key("refine_bullets", 
                                      experience_text=experience_text, 
                                      answers=answers)
        
        # Check cache first
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        # Make API call with retries
        result = self._make_request_with_retries("refine_bullets", 
                                               experience_text=experience_text, 
                                               answers=answers)
        
        # Cache the result
        self._set_cache(cache_key, result)
        
        return result
    
    def clear_cache(self):
        """Clear the entire cache."""
        self.cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        valid_entries = sum(1 for entry in self.cache.values() 
                          if self._is_cache_valid(entry))
        total_entries = len(self.cache)
        
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': total_entries - valid_entries,
            'cache_size_mb': sum(len(str(v)) for v in self.cache.values()) / (1024 * 1024)
        }
