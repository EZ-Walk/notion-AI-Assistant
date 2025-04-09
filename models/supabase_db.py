import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Supabase client
supabase: Client = None

def init_supabase():
    """
    Initialize the Supabase client with environment variables.
    When using RLS (Row Level Security), there are two approaches:
    1. Use service_role key to bypass RLS entirely (for backend services)
    2. Use anon key with JWT auth to work with RLS policies
    
    For this backend service, we use the service_role key to bypass RLS.
    """
    global supabase
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase_service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    # Check for required environment variables
    if not supabase_url:
        logger.error("Missing required environment variable: SUPABASE_URL")
        return False
    
    # Determine which key to use (prefer service role for backend services with RLS)
    if supabase_service_role:
        logger.info("Using service role key for Supabase authentication (bypasses RLS)")
        auth_key = supabase_service_role
    elif supabase_key:
        logger.warning("Using anon key for Supabase. Consider using SUPABASE_SERVICE_ROLE_KEY for backend services with RLS")
        auth_key = supabase_key
    else:
        logger.error("Missing required Supabase authentication keys: SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY")
        return False
    
    try:
        # Create client with the appropriate key
        supabase = create_client(supabase_url, auth_key)
        logger.info("Supabase client initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}")
        return False

def get_authenticated_client(notion_user_id=None):
    """
    Get an authenticated Supabase client.
    
    Args:
        notion_user_id (str, optional): The Notion user ID to get the client for.
            If None, returns a client with admin access using the service role key.
        
    Returns:
        Client: Authenticated Supabase client or None if error
    """
    if not supabase:
        logger.error("Main Supabase client not initialized")
        return None
    
    try:
        # If no user ID is provided, return a client with admin access
        if notion_user_id is None:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_service_role:
                logger.error("Missing required Supabase configuration for admin access")
                return None
                
            # Create an admin client with service role key
            admin_client = create_client(supabase_url, supabase_service_role)
            logger.info("Created Supabase admin client with service role key")
            return admin_client
        
        # Otherwise, get the user's access token from the subscriptions table
        response = supabase.table("subscriptions").select("access_token").eq("notion_user_id", notion_user_id).execute()
        
        if not response.data:
            logger.error(f"No subscription found for Notion user ID: {notion_user_id}")
            return None
            
        access_token = response.data[0].get('access_token')
        
        if not access_token:
            logger.error(f"No access token found for Notion user ID: {notion_user_id}")
            return None
            
        # Create a new client with the user's access token
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.error("Missing required Supabase configuration")
            return None
            
        # Create an authenticated client
        authenticated_client = create_client(supabase_url, supabase_key)
        
        # Set the user's access token
        # Note: This approach depends on how your Supabase auth is configured
        # For JWT auth, you might need to set the auth header differently
        authenticated_client.auth.set_auth(access_token)
        
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
    if not supabase:
        logger.error("Supabase client not initialized")
        return []
    
    try:
        response = supabase.table("subscriptions").select("*").execute()
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
    if not supabase:
        logger.error("Supabase client not initialized")
        return None
    
    try:
        # Check if comment already exists
        existing = supabase.table("comments").select("*").eq("id", comment_data["id"]).execute()
        
        if existing.data:
            # Update existing comment
            response = supabase.table("comments").update(comment_data).eq("id", comment_data["id"]).execute()
            logger.info(f"Updated comment: {comment_data['id']}")
        else:
            # Insert new comment
            response = supabase.table("comments").insert(comment_data).execute()
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
    if not supabase:
        logger.error("Supabase client not initialized")
        return []
    
    try:
        query = supabase.table("comments").select("*")
        
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
    if not supabase:
        logger.error("Supabase client not initialized")
        return False
    
    try:
        update_data = {
            "status": status,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        if error_message and status == 'error':
            update_data["error_message"] = error_message
            
        supabase.table("comments").update(update_data).eq("id", comment_id).execute()
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
    if not supabase:
        logger.error("Supabase client not initialized")
        return False
    
    try:
        # Check if the user ID exists in the subscriptions table
        response = supabase.table("subscriptions").select("*").eq("notion_user_id", notion_user_id).execute()
        
        # User is authorized if at least one subscription record is found
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error checking user authorization: {e}")
        return False
