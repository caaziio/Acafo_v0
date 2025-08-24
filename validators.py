import re
import html

def sanitize_text(text):
    """
    Sanitize user input text to prevent XSS and other injection attacks.
    
    Args:
        text (str): Raw user input text
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return ""
    
    # Convert to string if not already
    text = str(text)
    
    # HTML escape to prevent XSS
    text = html.escape(text)
    
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove any script-like content
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'vbscript:', '', text, flags=re.IGNORECASE)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def validate_bullet(text):
    """
    Validate and truncate bullet point text to 150 characters.
    
    Args:
        text (str): Bullet point text
        
    Returns:
        tuple: (truncated_text, was_truncated)
    """
    if not text:
        return "", False
    
    text = str(text).strip()
    
    if len(text) <= 150:
        return text, False
    
    # Truncate at 150 characters and add ellipsis
    truncated = text[:147] + "..."
    return truncated, True

def validate_bullets_list(bullets):
    """
    Validate and process a list of bullet points.
    
    Args:
        bullets (list): List of bullet point strings
        
    Returns:
        tuple: (processed_bullets, any_truncated)
    """
    if not bullets:
        return [], False
    
    processed_bullets = []
    any_truncated = False
    
    for bullet in bullets:
        truncated_bullet, was_truncated = validate_bullet(bullet)
        processed_bullets.append(truncated_bullet)
        if was_truncated:
            any_truncated = True
    
    return processed_bullets, any_truncated

def sanitize_bullets_for_save(bullets):
    """
    Sanitize bullet points for saving, removing control characters and enforcing limits.
    
    Args:
        bullets (list): List of bullet point strings
        
    Returns:
        list: Sanitized bullet points
    """
    if not bullets:
        return []
    
    sanitized_bullets = []
    
    for bullet in bullets:
        if not bullet:
            continue
            
        # Sanitize the text
        sanitized = sanitize_text(bullet)
        
        # Validate length
        validated, _ = validate_bullet(sanitized)
        
        if validated:
            sanitized_bullets.append(validated)
    
    return sanitized_bullets

def validate_story(text):
    """
    Validate story/experience text input.
    
    Args:
        text (str): User's experience story
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not text:
        return False, "Please provide your experience story."
    
    text = text.strip()
    
    if len(text) < 80:
        return False, "Please write at least 80 characters about your experience."
    
    if len(text) > 2000:
        return False, "Please keep your experience description under 2000 characters."
    
    return True, ""

def validate_answer(text):
    """
    Validate follow-up answer text.
    
    Args:
        text (str): User's answer to follow-up question
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not text:
        return False, "Please provide an answer."
    
    text = text.strip()
    
    if len(text) < 1:
        return False, "Please provide an answer."
    
    if len(text) > 500:
        return False, "Please keep your answer under 500 characters."
    
    return True, ""

def validate_experience_type(experience_type):
    """
    Validate experience type selection.
    
    Args:
        experience_type (str): Type of experience selected
        
    Returns:
        tuple: (is_valid, error_message)
    """
    valid_types = [
        "work_achievement", 
        "academic_project", 
        "volunteer_community", 
        "personal_challenge", 
        "hobby", 
        "other"
    ]
    
    if not experience_type:
        return False, "Please select an experience type."
    
    if experience_type.lower() not in valid_types:
        return False, "Please select a valid experience type."
    
    return True, ""
