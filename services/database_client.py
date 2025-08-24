import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from config import settings

logger = logging.getLogger(__name__)

class LazyDatabaseClient:
    """
    Lazy database client that only connects when data is actually needed.
    Maintains existing session-based functionality as primary method.
    Uses direct HTTP requests to avoid Supabase client compatibility issues.
    """
    
    def __init__(self):
        self._connected = False
        self._user_id: Optional[str] = None
        self._headers: Dict[str, str] = {}
        
    def _ensure_connection(self, user_id: str) -> bool:
        """Lazily establish database connection only when needed."""
        if self._connected and self._user_id == user_id:
            return True
            
        try:
            if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
                logger.warning("Supabase credentials not configured, falling back to session storage")
                return False
            
            # Set up headers for Supabase REST API
            self._headers = {
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
                "Content-Type": "application/json"
            }
            
            # Test the connection with a simple query
            try:
                test_url = f"{settings.SUPABASE_URL}/rest/v1/experiences?select=id&limit=1"
                response = httpx.get(test_url, headers=self._headers, timeout=10)
                
                if response.status_code in [200, 404]:  # 404 means table exists but no data
                    self._user_id = user_id
                    self._connected = True
                    logger.info(f"Database connection established for user {user_id}")
                    return True
                else:
                    logger.error(f"Database connection test failed with status {response.status_code}")
                    self._connected = False
                    return False
                    
            except Exception as test_error:
                logger.error(f"Database connection test failed: {test_error}")
                self._connected = False
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self._connected = False
            return False
    
    def _get_user_id_from_session(self, session_data: Dict[str, Any]) -> Optional[str]:
        """Extract user ID from session data."""
        return session_data.get('user_id')
    
    def save_experience(self, experience_data: Dict[str, Any], session_data: Dict[str, Any]) -> bool:
        """
        Save experience to database if connection available, otherwise return False.
        This allows the existing session logic to continue working.
        """
        user_id = self._get_user_id_from_session(session_data)
        if not user_id:
            return False
            
        if not self._ensure_connection(user_id):
            return False
            
        try:
            # Prepare data for database
            db_experience = {
                'user_id': user_id,
                'title': experience_data.get('title', ''),
                'experience_text': experience_data.get('experience_text', ''),
                'bullets': json.dumps(experience_data.get('bullets', [])),
                'skills': json.dumps(experience_data.get('skills', [])),
                'experience_type': experience_data.get('experience_type', ''),
                'start_date': experience_data.get('start_date', None),
                'end_date': experience_data.get('end_date', None),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Try to insert into database using REST API
            insert_url = f"{settings.SUPABASE_URL}/rest/v1/experiences"
            response = httpx.post(insert_url, json=db_experience, headers=self._headers, timeout=10)
            
            if response.status_code == 201:
                logger.info(f"Experience saved to database for user {user_id}")
                return True
            else:
                logger.warning(f"Failed to save experience to database: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Database save error: {e}")
            return False
    
    def load_experiences(self, session_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Load experiences from database if connection available and session is empty.
        Returns None if database is not available, allowing session fallback.
        """
        user_id = self._get_user_id_from_session(session_data)
        if not user_id:
            return None
            
        # Only try database if session doesn't have experiences
        if session_data.get('experience_list'):
            return None
            
        if not self._ensure_connection(user_id):
            return None
            
        try:
            # Query experiences using REST API
            query_url = f"{settings.SUPABASE_URL}/rest/v1/experiences?user_id=eq.{user_id}&order=created_at.desc"
            response = httpx.get(query_url, headers=self._headers, timeout=10)
            
            if response.status_code == 200:
                db_experiences = response.json()
                
                if db_experiences:
                    # Convert database format back to session format
                    experiences = []
                    for db_exp in db_experiences:
                        experience = {
                            'id': db_exp.get('id'),
                            'title': db_exp.get('title', ''),
                            'experience_text': db_exp.get('experience_text', ''),
                            'bullets': json.loads(db_exp.get('bullets', '[]')),
                            'skills': json.loads(db_exp.get('skills', '[]')),
                            'created_at': db_exp.get('created_at'),
                            'start_date': db_exp.get('start_date'),
                            'end_date': db_exp.get('end_date'),
                        }
                        experiences.append(experience)
                    
                    logger.info(f"Loaded {len(experiences)} experiences from database for user {user_id}")
                    return experiences
                else:
                    return []
            else:
                logger.warning(f"Failed to load experiences from database: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Database load error: {e}")
            return None
    
    def delete_experience(self, experience_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Delete experience from database if connection available.
        Returns True if deleted from database, False otherwise.
        """
        user_id = self._get_user_id_from_session(session_data)
        if not user_id:
            return False
            
        if not self._ensure_connection(user_id):
            return False
            
        try:
            # Delete experience using REST API
            delete_url = f"{settings.SUPABASE_URL}/rest/v1/experiences?id=eq.{experience_id}&user_id=eq.{user_id}"
            response = httpx.delete(delete_url, headers=self._headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Experience {experience_id} deleted from database for user {user_id}")
                return True
            else:
                logger.warning(f"Failed to delete experience {experience_id} from database: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Database delete error: {e}")
            return False
    
    def update_experience(self, experience_id: str, experience_data: Dict[str, Any], session_data: Dict[str, Any]) -> bool:
        """
        Update experience in database if connection available.
        Returns True if updated in database, False otherwise.
        """
        user_id = self._get_user_id_from_session(session_data)
        if not user_id:
            return False
            
        if not self._ensure_connection(user_id):
            return False
            
        try:
            update_data = {
                'title': experience_data.get('title', ''),
                'experience_text': experience_data.get('experience_text', ''),
                'bullets': json.dumps(experience_data.get('bullets', [])),
                'skills': json.dumps(experience_data.get('skills', [])),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Update experience using REST API
            update_url = f"{settings.SUPABASE_URL}/rest/v1/experiences?id=eq.{experience_id}&user_id=eq.{user_id}"
            response = httpx.patch(update_url, json=update_data, headers=self._headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Experience {experience_id} updated in database for user {user_id}")
                return True
            else:
                logger.warning(f"Failed to update experience {experience_id} in database: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Database update error: {e}")
            return False
    
    def save_ai_log(self, log_data: Dict[str, Any], session_data: Dict[str, Any]) -> bool:
        """
        Save AI call log to database if connection available.
        Returns True if saved to database, False otherwise.
        """
        user_id = self._get_user_id_from_session(session_data)
        if not user_id:
            return False
            
        if not self._ensure_connection(user_id):
            return False
            
        try:
            db_log = {
                'user_id': user_id,
                'request_id': log_data.get('request_id', ''),
                'session_id': log_data.get('session_id', ''),
                'method': log_data.get('method', ''),
                'experience_type': log_data.get('experience_type', ''),
                'text_length': log_data.get('text_length', 0),
                'text_hash': log_data.get('text_hash', ''),
                'elapsed_ms': log_data.get('elapsed_ms', 0),
                'success': log_data.get('success', True),
                'error': log_data.get('error', ''),
                'timestamp': log_data.get('timestamp', datetime.utcnow().isoformat())
            }
            
            # Try to insert into database using REST API
            insert_url = f"{settings.SUPABASE_URL}/rest/v1/ai_logs"
            response = httpx.post(insert_url, json=db_log, headers=self._headers, timeout=10)
            
            if response.status_code == 201:
                logger.info(f"AI log saved to database for user {user_id}")
                return True
            else:
                logger.warning(f"Failed to save AI log to database: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Database AI log save error: {e}")
            return False

    def save_career_goal(self, goal_data: Dict[str, Any], session_data: Dict[str, Any]) -> bool:
        """
        Save career goal to database if connection available, otherwise return False.
        """
        user_id = self._get_user_id_from_session(session_data)
        if not user_id:
            return False
        if not self._ensure_connection(user_id):
            return False
        try:
            db_goal = {
                'user_id': user_id,
                'target_role': goal_data.get('target_role', ''),
                'industry': goal_data.get('industry', ''),
                'location': goal_data.get('location', ''),
                'timeline': goal_data.get('timeline', ''),
                'korean_level': goal_data.get('korean_level', ''),
                'other_languages': json.dumps(goal_data.get('other_languages', [])),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            insert_url = f"{settings.SUPABASE_URL}/rest/v1/career_goals"
            response = httpx.post(insert_url, json=db_goal, headers=self._headers, timeout=10)
            if response.status_code == 201:
                logger.info(f"Career goal saved to database for user {user_id}")
                return True
            else:
                logger.warning(f"Failed to save career goal to database: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Database save error (career goal): {e}")
            return False

    def load_career_goal(self, session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Load the latest career goal for the user from the database.
        """
        user_id = self._get_user_id_from_session(session_data)
        if not user_id:
            return None
        if not self._ensure_connection(user_id):
            return None
        try:
            query_url = f"{settings.SUPABASE_URL}/rest/v1/career_goals?user_id=eq.{user_id}&order=created_at.desc&limit=1"
            response = httpx.get(query_url, headers=self._headers, timeout=10)
            if response.status_code == 200:
                goals = response.json()
                if goals:
                    db_goal = goals[0]
                    return {
                        'target_role': db_goal.get('target_role', ''),
                        'industry': db_goal.get('industry', ''),
                        'location': db_goal.get('location', ''),
                        'timeline': db_goal.get('timeline', ''),
                        'korean_level': db_goal.get('korean_level', ''),
                        'other_languages': json.loads(db_goal.get('other_languages', '[]')),
                        'created_at': db_goal.get('created_at'),
                        'updated_at': db_goal.get('updated_at')
                    }
                else:
                    return None
            else:
                logger.warning(f"Failed to load career goal from database: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Database load error (career goal): {e}")
            return None

# Global instance
lazy_db = LazyDatabaseClient()
