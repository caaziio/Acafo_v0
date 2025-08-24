import os
import httpx
from typing import Optional, Dict, Any

class SupabaseClient:
    """Simplified Supabase client wrapper for authentication using direct HTTP requests."""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not self.url or not self.anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")
        
        # Remove trailing slash if present
        self.url = self.url.rstrip('/')
        self.base_url = f"{self.url}/auth/v1"
        
        self.headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json"
        }
    
    def auth_sign_in_with_oauth(self, provider: str, redirect_to: str) -> Dict[str, Any]:
        """Sign in with OAuth provider (Google, GitHub, etc.)."""
        try:
            oauth_url = f"{self.base_url}/authorize"
            params = {
                "provider": provider,
                "redirect_to": redirect_to
            }
            
            response = httpx.get(oauth_url, params=params, headers=self.headers)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def auth_sign_in_with_otp(self, email: str, redirect_to: str) -> Dict[str, Any]:
        """Send magic link to user's email."""
        try:
            otp_url = f"{self.base_url}/otp"
            data = {
                "email": email,
                "type": "magiclink"
            }
            
            # Add redirect_to as a query parameter instead of in the body
            params = {
                "redirect_to": redirect_to
            }
            
            response = httpx.post(otp_url, json=data, params=params, headers=self.headers)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def auth_get_user(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information from access token."""
        try:
            user_url = f"{self.base_url}/user"
            headers = {
                **self.headers,
                "Authorization": f"Bearer {access_token}"
            }
            
            response = httpx.get(user_url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception:
            return None
    
    def auth_sign_out(self) -> Dict[str, Any]:
        """Sign out the current user."""
        try:
            logout_url = f"{self.base_url}/logout"
            response = httpx.post(logout_url, headers=self.headers)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

# Global instance
supabase_client = None

def get_supabase_client() -> SupabaseClient:
    """Get or create the global Supabase client instance."""
    global supabase_client
    if supabase_client is None:
        supabase_client = SupabaseClient()
    return supabase_client
