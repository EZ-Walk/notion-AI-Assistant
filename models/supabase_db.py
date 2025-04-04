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
    """
    global supabase
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.error("Missing required Supabase environment variables: SUPABASE_URL and/or SUPABASE_KEY")
        return False
    
    try:
        supabase = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}")
        return False

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
