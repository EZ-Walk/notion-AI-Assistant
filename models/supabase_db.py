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

def save_comment(comment_data):
    """
    Save a comment to the Supabase database.
    
    Args:
        comment_data (dict): Comment data to save
        
    Returns:
        dict: The saved comment data or None if error
    """
    client = get_supabase_client()
    if not client:
        logger.error("Failed to get Supabase client")
        return None
    
    try:
        # Check if comment already exists
        existing = client.table("comments").select("*").eq("id", comment_data["id"]).execute()
        
        if existing.data:
            # Update existing comment
            response = client.table("comments").update(comment_data).eq("id", comment_data["id"]).execute()
            logger.info(f"Updated comment: {comment_data['id']}")
        else:
            # Insert new comment
            response = client.table("comments").insert(comment_data).execute()
            logger.info(f"Added new comment: {comment_data['id']}")
        
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error saving comment: {e}")
        return None

def get_comments(discussion_id=None, parent_id=None, status=None):
    """
    Get comments from the Supabase database with optional filters.
    
    Args:
        discussion_id (str, optional): Filter by discussion ID
        parent_id (str, optional): Filter by parent ID
        status (str, optional): Filter by status
        
    Returns:
        list: List of comment records matching the filters
    """
    client = get_supabase_client()
    if not client:
        logger.error("Failed to get Supabase client")
        return []
    
    try:
        query = client.table("comments").select("*")
        
        if discussion_id:
            query = query.eq("discussion_id", discussion_id)
        
        if parent_id:
            query = query.eq("parent_id", parent_id)
        
        if status:
            query = query.eq("status", status)
        
        response = query.execute()
        return response.data
    except Exception as e:
        logger.error(f"Error fetching comments: {e}")
        return []

def update_comment_status(comment_id, status, error_message=None):
    """
    Update the status of a comment in the Supabase database.
    
    Args:
        comment_id (str): The ID of the comment
        status (str): New status for the comment
        error_message (str, optional): Error message if status is 'error'
        
    Returns:
        bool: True if successful, False otherwise
    """
    client = get_supabase_client()
    if not client:
        logger.error("Failed to get Supabase client")
        return False
    
    try:
        update_data = {
            "status": status,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        if error_message and status == 'error':
            update_data["error_message"] = error_message
            
        client.table("comments").update(update_data).eq("id", comment_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error updating comment status: {e}")
        return False

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
