import os
import json
import gspread
from datetime import datetime
from config import settings

def ensure_logs_directory():
    """Ensure the logs directory exists."""
    os.makedirs(settings.LOGS_DIR, exist_ok=True)

def write_json_log(data):
    """
    Write data to a JSON log file with timestamp.
    
    Args:
        data (dict): Data to log
    """
    try:
        ensure_logs_directory()
        
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"log_{timestamp}.json"
        filepath = os.path.join(settings.LOGS_DIR, filename)
        
        # Add timestamp to data
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            **data
        }
        
        # Write to JSON file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)
            
        print(f"Logged to JSON file: {filepath}")
        
    except Exception as e:
        print(f"Error writing JSON log: {e}")

def write_to_google_sheets(data):
    """
    Write data to Google Sheets if credentials are available.
    
    Args:
        data (dict): Data to log with keys: title, story, bullet_before, 
                    answers, bullet_after, skills, suggestions
    """
    try:
        # Check if credentials file exists
        if not os.path.exists(settings.GOOGLE_CREDENTIALS_PATH):
            print(f"Warning: Google credentials file not found at {settings.GOOGLE_CREDENTIALS_PATH}")
            print("Skipping Google Sheets logging")
            return False
        
        # Check if Google Sheet URL is configured
        if not settings.GOOGLE_SHEET_URL:
            print("Warning: GOOGLE_SHEET_URL not configured")
            print("Skipping Google Sheets logging")
            return False
        
        # Clean and format data
        bullet_before = data.get('bullet_before', '').replace("*", "").strip()
        bullet_after = data.get('bullet_after', '').replace("*", "").strip()
        bullet_before = bullet_before.replace("\n", " • ")
        bullet_after = bullet_after.replace("\n", " • ")
        skills = data.get('skills', '').replace("\n", ", ")
        suggestions = data.get('suggestions', '').replace("*", "").strip().replace("\n", " • ")
        
        # Get timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare row
        row = [
            timestamp,
            data.get('title', ''),
            data.get('story', ''),
            bullet_before,
            data.get('answers', [''])[0] if data.get('answers') else '',
            data.get('answers', [''])[1] if len(data.get('answers', [])) > 1 else '',
            data.get('answers', [''])[2] if len(data.get('answers', [])) > 2 else '',
            bullet_after,
            skills,
            suggestions
        ]
        
        # Send to Google Sheet
        gc = gspread.service_account(filename=settings.GOOGLE_CREDENTIALS_PATH)
        sheet = gc.open_by_url(settings.GOOGLE_SHEET_URL)
        worksheet = sheet.sheet1
        worksheet.append_row(row)
        
        print("Successfully logged to Google Sheets")
        return True
        
    except Exception as e:
        print(f"Error writing to Google Sheets: {e}")
        print("Falling back to JSON logging only")
        return False

def log_to_google_sheet(
    title,
    story,
    bullet_before,
    answers,
    bullet_after,
    skills,
    suggestions
):
    """
    Legacy function for backward compatibility.
    Logs data to both Google Sheets and JSON files.
    """
    data = {
        'title': title,
        'story': story,
        'bullet_before': bullet_before,
        'answers': answers,
        'bullet_after': bullet_after,
        'skills': skills,
        'suggestions': suggestions
    }
    
    # Always write to JSON log
    write_json_log(data)
    
    # Try to write to Google Sheets
    write_to_google_sheets(data)