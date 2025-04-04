import logging
from datetime import datetime
from models.supabase_db import save_comment, get_comments, update_comment_status

logger = logging.getLogger(__name__)

class SupabaseCommentService:
    """
    Service for handling Notion comment operations and Supabase database interactions.
    """
    
    @staticmethod
    def save_comments_to_db(comments):
        """
        Save a list of Notion comments to the Supabase database.
        
        Args:
            comments (list): List of comment objects from Notion API
            
        Returns:
            dict: Dictionary with counts of new, updated, and unchanged comments
        """
        result = {
            "new": 0,
            "updated": 0,
            "unchanged": 0
        }
        
        try:
            for comment in comments:
                # Extract comment data
                comment_id = comment["id"]
                discussion_id = comment.get("discussion_id")
                
                # Determine parent type and ID
                parent_type = None
                parent_id = None
                if "parent" in comment:
                    if "page_id" in comment["parent"]:
                        parent_type = "page"
                        parent_id = comment["parent"]["page_id"]
                    elif "block_id" in comment["parent"]:
                        parent_type = "block"
                        parent_id = comment["parent"]["block_id"]
                
                # Extract text content
                plain_text = ""
                if "rich_text" in comment and len(comment["rich_text"]) > 0:
                    plain_text = comment["rich_text"][0].get("text", {}).get("content", "")
                
                # Extract timestamps
                created_time = comment.get("created_time", datetime.utcnow().isoformat())
                last_edited_time = comment.get("last_edited_time")
                
                # Extract user ID
                created_by_id = None
                if "created_by" in comment and "id" in comment["created_by"]:
                    created_by_id = comment["created_by"]["id"]
                
                # Prepare comment data for Supabase
                comment_data = {
                    "id": comment_id,
                    "discussion_id": discussion_id,
                    "parent_type": parent_type,
                    "parent_id": parent_id,
                    "plain_text": plain_text,
                    "created_time": created_time,
                    "last_edited_time": last_edited_time,
                    "created_by_id": created_by_id,
                    "status": "new"
                }
                
                # Check if we're updating an existing comment or creating a new one
                existing_comments = get_comments(None, None, None)
                existing_comment = next((c for c in existing_comments if c["id"] == comment_id), None)
                
                if not existing_comment:
                    # Case 1: Comment doesn't exist in database, add it
                    save_comment(comment_data)
                    result["new"] += 1
                    logger.info(f"Added new comment: {comment_id}")
                    
                elif existing_comment.get("last_edited_time") and last_edited_time and last_edited_time > existing_comment.get("last_edited_time"):
                    # Case 2: Comment exists but has been updated (newer last_edited_time)
                    comment_data["status"] = "updated"
                    save_comment(comment_data)
                    result["updated"] += 1
                    logger.info(f"Updated comment: {comment_id}")
                    
                else:
                    # Case 3: Comment exists and hasn't changed
                    result["unchanged"] += 1
            
            return result 
        except Exception as e:
            logger.error(f"Error saving comments to database: {e}")
            return {"new": 0, "updated": 0, "unchanged": 0, "error": str(e)}
    
    @staticmethod
    def get_new_comments():
        """
        Get all new comments from the database.
        
        Returns:
            list: List of Comment objects with status 'new'
        """
        return get_comments(None, None, "new")
    
    @staticmethod
    def mark_comment_as_processed(comment_id):
        """
        Mark a comment as processed in the database.
        
        Args:
            comment_id (str): The ID of the comment to mark as processed
            
        Returns:
            bool: True if successful, False otherwise
        """
        return update_comment_status(comment_id, "processed")
    
    @staticmethod
    def mark_comment_as_error(comment_id, error_message=None):
        """
        Mark a comment as having an error during processing.
        
        Args:
            comment_id (str): The ID of the comment
            error_message (str, optional): Error message to log
            
        Returns:
            bool: True if successful, False otherwise
        """
        return update_comment_status(comment_id, "error", error_message)
    
    @staticmethod
    def get_comments_from_db(discussion_id=None, parent_id=None, status=None):
        """
        Get comments from the database with optional filters.
        
        Args:
            discussion_id (str, optional): Filter by discussion ID
            parent_id (str, optional): Filter by parent ID
            status (str, optional): Filter by status
            
        Returns:
            list: List of Comment objects matching the filters
        """
        return get_comments(discussion_id, parent_id, status)
