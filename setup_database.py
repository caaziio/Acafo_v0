#!/usr/bin/env python3
"""
Database setup script for Resume Builder
This script helps initialize the database tables and test the connection.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.database_client import lazy_db
from config import settings

def test_database_connection():
    """Test the database connection."""
    print("Testing database connection...")
    
    try:
        # Test with a dummy user ID
        test_user_id = "test-user-123"
        test_session = {"user_id": test_user_id}
        
        # This will attempt to connect
        connected = lazy_db._ensure_connection(test_user_id)
        
        if connected:
            print("✅ Database connection successful!")
            return True
        else:
            print("❌ Database connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def check_environment():
    """Check if required environment variables are set."""
    print("Checking environment variables...")
    
    required_vars = ["SUPABASE_URL", "SUPABASE_ANON_KEY"]
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 10)}...")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\nMissing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return False
    
    return True

def main():
    """Main setup function."""
    print("🚀 Resume Builder Database Setup")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please fix the issues above.")
        return
    
    print("\n" + "=" * 40)
    
    # Test database connection
    if test_database_connection():
        print("\n✅ Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Run the SQL commands in database_schema.sql in your Supabase dashboard")
        print("2. Test the application to ensure database operations work")
        print("3. Monitor the logs for any database-related errors")
    else:
        print("\n❌ Database setup failed. Please check your Supabase configuration.")
        print("\nTroubleshooting:")
        print("1. Verify your Supabase URL and API key")
        print("2. Check if your Supabase project is active")
        print("3. Ensure the database is accessible")

if __name__ == "__main__":
    main()

