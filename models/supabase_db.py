import os
import logging
from datetime import datetime
from supabase import create_client, Client
from functools import lru_cache

logger = logging.getLogger(__name__)

# Supabase client
_supabase_client: Client = None

@lru_cache(maxsize=1)
def get_supabase_client():
    """
    Initialize and return the Supabase admin client with service role key.
    Uses LRU cache to ensure only one client instance is created.
    
    Returns:
        Client: Authenticated Supabase admin client or None if error
    """
    global _supabase_client
    
    # Return existing client if already initialized
    if _supabase_client is not None:
        return _supabase_client
    
    # Get environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    # Check for required environment variables
    if not supabase_url:
        logger.error("Missing required environment variable: SUPABASE_URL")
        return None
    
    if not supabase_service_role:
        logger.error("Missing required environment variable: SUPABASE_SERVICE_ROLE_KEY")
        return None
    
    try:
        # Create admin client with service role key (bypasses RLS)
        _supabase_client = create_client(supabase_url, supabase_service_role)
        logger.info("Supabase admin client initialized successfully")
        return _supabase_client
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}")
        return None
        
        # Set the user's access token
        # Note: This approach depends on how your Supabase auth is configured
        # For JWT auth, you might need to set the auth header differently
        # authenticated_client.auth.set_auth(access_token)
        
        logger.info(f"Created authenticated Supabase client for Notion user ID: {notion_user_id}")
        return authenticated_client
        
    except Exception as e:
        logger.error(f"Error creating authenticated Supabase client: {e}")
        return None

def get_subscriptions():
    """
    Get all subscriptions from the Supabase database.
    
    Returns:
        list: List of subscription records
    """
    client = get_supabase_client()
    if not client:
        logger.error("Failed to get Supabase client")
        return []
    
    try:
        response = client.table("subscriptions").select("*").execute()
        return response.data
    except Exception as e:
        logger.error(f"Error fetching subscriptions: {e}")
        return []

def is_user_authorized(notion_user_id):
    """
    Check if a user is authorized based on their Notion user ID.
    
    Args:
        notion_user_id (str): The Notion user ID to check
        
    Returns:
        bool: True if the user is authorized, False otherwise
    """
    client = get_supabase_client()
    if not client:
        logger.error("Failed to get Supabase client")
        return False
    
    try:
        # Check if the user ID exists in the subscriptions table
        response = client.table("subscriptions").select("*").eq("notion_user_id", notion_user_id).execute()
        
        # User is authorized if at least one subscription record is found
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error checking user authorization: {e}")
        return False
