import os
from dotenv import load_dotenv

# Load environment variables from .env file, fallback to os.environ
load_dotenv()

class Settings:
    """Centralized configuration settings for the Flask resume builder app."""
    
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    IS_PRODUCTION = ENVIRONMENT == "production"
    
    # Flask app settings
    APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-key-change-in-production")
    SESSION_TYPE = os.getenv("SESSION_TYPE", "filesystem")
    
    # Supabase settings
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Add this for production
    
    # Site URL for redirects (production vs development)
    SITE_URL = os.getenv("SITE_URL", "http://localhost:3000")
    
    # OpenAI API settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "2000"))
    AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
    
    # Google Sheets settings
    GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    
    # Rate limiting settings
    RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "100 per minute")
    RATE_LIMIT_AI = os.getenv("RATE_LIMIT_AI", "10 per minute")
    
    # Logging settings
    LOGS_DIR = os.getenv("LOGS_DIR", "logs")
    
    @classmethod
    def validate(cls):
        """Validate that required settings are present."""
        required_settings = ["OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY"]
        
        # Add service role key requirement for production
        if cls.IS_PRODUCTION:
            required_settings.append("SUPABASE_SERVICE_ROLE_KEY")
            required_settings.append("SITE_URL")
        
        missing = []
        
        for setting in required_settings:
            if not getattr(cls, setting):
                missing.append(setting)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True

# Create settings instance
settings = Settings()

# Validate settings on import
try:
    settings.validate()
except ValueError as e:
    print(f"Configuration error: {e}")
    print("Please check your .env file or environment variables.")
