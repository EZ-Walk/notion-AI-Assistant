import os
import time
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify
from dotenv import load_dotenv
from notion_client import Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Notion API configuration
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_VERSION = "2022-06-28"  # Notion API version

# Initialize Notion client
notion = Client(auth=NOTION_API_KEY, notion_version=NOTION_VERSION)

# No longer using OpenAI

# Get configuration from environment variables
# NOTION_PAGE_ID is now optional and only used if you want to limit to a specific page
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID", None)
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "3"))  # Default to 3 seconds
PORT = int(os.getenv("PORT", "5001"))  # Default to port 5001

# Check for required environment variables
required_vars = ["NOTION_API_KEY"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these variables in your .env file. See .env.sample for reference.")

# Flag to control polling
POLLING_ACTIVE = True

class DiscussionPool:
    """A pool of discussions organized by parent ID and discussion ID.
    
    This class provides a structured way to store and access discussions and their messages.
    Each discussion is identified by a parent_id (page or block) and a discussion_id.
    Messages within discussions have status tracking.
    """
    def __init__(self):
        # Structure: {parent_id: {discussion_id: {message_id: {message_data, status}}}}
        self.discussions = {}
    
    def add_message(self, parent_id, discussion_id, message_id, message_data, status="received"):
        """Add a message to the discussion pool.
        
        Args:
            parent_id: ID of the parent page or block
            discussion_id: ID of the discussion thread
            message_id: ID of the message
            message_data: The message data from Notion API
            status: Status of the message (received, processing, sent, error)
        """
        # Initialize nested dictionaries if needed
        if parent_id not in self.discussions:
            self.discussions[parent_id] = {}
        if discussion_id not in self.discussions[parent_id]:
            self.discussions[parent_id][discussion_id] = {}
        
        # Add message with status
        self.discussions[parent_id][discussion_id][message_id] = {
            "data": message_data,
            "status": status
        }
        
        # Print the current state of the discussion pool
        self.print_pool()
    
    def update_message_status(self, parent_id, discussion_id, message_id, status):
        """Update the status of a message.
        
        Args:
            parent_id: ID of the parent page or block
            discussion_id: ID of the discussion thread
            message_id: ID of the message
            status: New status of the message
        """
        if (parent_id in self.discussions and 
            discussion_id in self.discussions[parent_id] and 
            message_id in self.discussions[parent_id][discussion_id]):
            self.discussions[parent_id][discussion_id][message_id]["status"] = status
            # Print the current state of the discussion pool
            self.print_pool()
    
    def get_message(self, parent_id, discussion_id, message_id):
        """Get a message from the discussion pool.
        
        Args:
            parent_id: ID of the parent page or block
            discussion_id: ID of the discussion thread
            message_id: ID of the message
            
        Returns:
            The message data or None if not found
        """
        if (parent_id in self.discussions and 
            discussion_id in self.discussions[parent_id] and 
            message_id in self.discussions[parent_id][discussion_id]):
            return self.discussions[parent_id][discussion_id][message_id]
        return None
    
    def get_discussion(self, parent_id, discussion_id):
        """Get all messages in a discussion.
        
        Args:
            parent_id: ID of the parent page or block
            discussion_id: ID of the discussion thread
            
        Returns:
            Dictionary of messages in the discussion or empty dict if not found
        """
        if (parent_id in self.discussions and 
            discussion_id in self.discussions[parent_id]):
            return self.discussions[parent_id][discussion_id]
        return {}
    
    def print_pool(self):
        """Print the current state of the discussion pool."""
        logger.info(f"Discussion Pool: {len(self.discussions)} parent pages/blocks")
        for parent_id, discussions in self.discussions.items():
            logger.info(f"  Parent {parent_id}: {len(discussions)} discussions")
            for discussion_id, messages in discussions.items():
                logger.info(f"    Discussion {discussion_id}: {len(messages)} messages")
                for message_id, message in messages.items():
                    logger.info(f"      Message {message_id}: status={message['status']}")

# Initialize the discussion pool
discussion_pool = DiscussionPool()

def get_comments_from_page(block_id=None):
    """Retrieve all open (un-resolved) comments from Notion.
    
    If block_id is provided, only comments from that specific page/block will be retrieved.
    Otherwise, all accessible comments will be retrieved.
    
    According to Notion API docs, this endpoint returns a flatlist of comments associated 
    with the ID provided. Multiple discussion threads may be included in the response,
    with comments from all threads returned in ascending chronological order.
    """
    try:
        # Get comments using the Notion SDK
        if block_id:
            response = notion.comments.list(block_id=block_id)
            logger.info(f"Retrieved comments from specific Notion page/block: {block_id}")
        else:
            # Without a block_id, we'll get all accessible comments
            # Note: This uses the search endpoint to find pages with comments
            # and then collects comments from each page
            all_comments = []
            
            # Search for pages with comments
            search_response = notion.search(filter={"property": "object", "value": "page"})
            pages = search_response.get("results", [])
            
            logger.info(f"Found {len(pages)} pages to check for comments")
            
            # Get comments from each page
            for page in pages:
                page_id = page.get("id")
                try:
                    page_comments_response = notion.comments.list(block_id=page_id)
                    page_comments = page_comments_response.get("results", [])
                    all_comments.extend(page_comments)
                    if page_comments:
                        logger.info(f"Retrieved {len(page_comments)} comments from page {page_id}")
                except Exception as page_error:
                    logger.warning(f"Error retrieving comments from page {page_id}: {page_error}")
                    continue
            
            logger.info(f"Retrieved a total of {len(all_comments)} comments from all accessible pages")
            return all_comments
        
        # Return the results, which is a flatlist of comments
        comments = response.get("results", [])
        logger.info(f"Retrieved {len(comments)} comments")
        return comments
    except Exception as e:
        logger.error(f"Error retrieving comments from Notion: {e}")
        return []

def process_comment(comment, parent_id=None):
    """Process a single comment by simply echoing it back.
    
    This simplified function just extracts the comment text and sends it back as a reply.
    The comment and its echo response are added to the Discussion Pool for tracking.
    """
    try:
        # Extract comment information
        comment_id = comment["id"]
        discussion_id = comment.get("discussion_id")
        
        # Extract comment text
        comment_text = ""
        if "rich_text" in comment and len(comment["rich_text"]) > 0:
            comment_text = comment["rich_text"][0].get("text", {}).get("content", "")
        
        # Determine parent ID for the reply (could be page_id or block_id)
        parent_id = None
        if "parent" in comment:
            if "page_id" in comment["parent"]:
                parent_id = comment["parent"]["page_id"]
            elif "block_id" in comment["parent"]:
                parent_id = comment["parent"]["block_id"]
        
        # Skip processing if missing essential information
        if not parent_id or not comment_text:
            logger.warning(f"Skipping comment {comment_id}: Missing parent_id or comment_text")
            return
            
        # Add the original comment to the Discussion Pool
        discussion_pool.add_message(
            parent_id=parent_id,
            discussion_id=discussion_id,
            message_id=comment_id,
            message_data=comment,
            status="received"
        )
        
        logger.info(f"Echoing comment: {comment_id} from discussion: {discussion_id}")
        logger.info(f"Comment text: {comment_text}")
        
        # Prepare the echo response
        rich_text = [{
            "type": "text",
            "text": {
                "content": f"Echo: {comment_text}"
            }
        }]
        
        # Post the echo response as a reply using the Notion SDK
        try:
            parent_dict = {}
            
            # Set either page_id or block_id, but not both
            if "page_id" in comment.get("parent", {}):
                parent_dict = {"page_id": parent_id}
                logger.info(f"Creating comment on page {parent_id}")
            else:
                parent_dict = {"block_id": parent_id}
                logger.info(f"Creating comment on block {parent_id}")
            
            # Create the comment
            response = notion.comments.create(
                parent=parent_dict,
                rich_text=rich_text
            )
            logger.info(f"Echo comment created successfully: {response}")
            
            # Add the echo response to the Discussion Pool
            if response and "id" in response:
                echo_id = response["id"]
                discussion_pool.add_message(
                    parent_id=parent_id,
                    discussion_id=discussion_id,
                    message_id=echo_id,
                    message_data=response,
                    status="sent"
                )
            
        except Exception as e:
            logger.error(f"Error creating comment: {e}")
            # Update the status of the original message in the Discussion Pool
            discussion_pool.update_message_status(
                parent_id=parent_id,
                discussion_id=discussion_id,
                message_id=comment_id,
                status="error_processing"
            )
            
            # Try with discussion_id if the first attempt failed and we have a discussion_id
            if discussion_id:
                try:
                    logger.info(f"Trying again with discussion_id parameter")
                    parent_dict = {}
                    if "page_id" in comment.get("parent", {}):
                        parent_dict = {"page_id": parent_id}
                    else:
                        parent_dict = {"block_id": parent_id}
                        
                    response = notion.comments.create(
                        parent=parent_dict,
                        discussion_id=discussion_id,
                        rich_text=rich_text
                    )
                    logger.info(f"Echo comment created with discussion_id parameter: {response}")
                    
                    # Add the echo response to the Discussion Pool
                    if response and "id" in response:
                        echo_id = response["id"]
                        discussion_pool.add_message(
                            parent_id=parent_id,
                            discussion_id=discussion_id,
                            message_id=echo_id,
                            message_data=response,
                            status="sent_with_discussion_id"
                        )
                        
                    # Update the status of the original message
                    discussion_pool.update_message_status(
                        parent_id=parent_id,
                        discussion_id=discussion_id,
                        message_id=comment_id,
                        status="processed"
                    )
                    
                except Exception as e2:
                    logger.error(f"Second attempt to create comment failed: {e2}")
                    # Update the status of the original message
                    discussion_pool.update_message_status(
                        parent_id=parent_id,
                        discussion_id=discussion_id,
                        message_id=comment_id,
                        status="failed"
                    )
                    raise
            else:
                # If there's no discussion_id and the first attempt failed, re-raise the exception
                # Update the status of the original message
                discussion_pool.update_message_status(
                    parent_id=parent_id,
                    discussion_id=discussion_id,
                    message_id=comment_id,
                    status="failed"
                )
                raise
        
        # Mark this comment as processed
        processed_comments.add(comment_id)
        
        # Update the status of the original message
        discussion_pool.update_message_status(
            parent_id=parent_id,
            discussion_id=discussion_id,
            message_id=comment_id,
            status="processed"
        )
        
        logger.info(f"Successfully echoed comment {comment_id}")
        
    except Exception as e:
        logger.error(f"Error echoing comment {comment.get('id', 'unknown')}: {e}")


def get_unprocessed_comments(comments):
    """Filter out already processed comments using the Discussion Pool.
    
    Args:
        comments: A list of comments from the Notion API
        
    Returns:
        A list of comments that haven't been processed yet
    """
    unprocessed = []
    
    for comment in comments:
        comment_id = comment.get("id")
        parent_id = None
        discussion_id = comment.get("discussion_id", "unthreaded")
        
        # Determine parent ID for the comment
        if "parent" in comment:
            if "page_id" in comment["parent"]:
                parent_id = comment["parent"]["page_id"]
            elif "block_id" in comment["parent"]:
                parent_id = comment["parent"]["block_id"]
        
        # Skip if no parent_id found
        if not parent_id:
            logger.warning(f"Skipping comment {comment_id}: Missing parent_id")
            continue
        
        # Check if the comment is already in the Discussion Pool
        message = discussion_pool.get_message(parent_id, discussion_id, comment_id)
        
        # If the comment is not in the Discussion Pool and not in processed_comments, add it to unprocessed
        if not message and comment_id not in processed_comments:
            unprocessed.append(comment)
    
    logger.info(f"Found {len(unprocessed)} unprocessed comments out of {len(comments)} total comments")
    return unprocessed


def process_comments(comments):
    """Process a list of comments sequentially.
    
    Args:
        comments: A list of comments to process
    """
    # Process each comment sequentially
    for comment in comments:
        process_comment(comment)

def poll_notion_page():
    """Poll Notion for new comments and process them.
    
    Retrieves all open (un-resolved) comments from either a specific page/block (if NOTION_PAGE_ID is set)
    or from all accessible pages. Filters out already processed comments, and processes each unprocessed comment sequentially.
    Comments are automatically added to the Discussion Pool during processing.
    """
    if NOTION_PAGE_ID:
        logger.info(f"Polling specific Notion page {NOTION_PAGE_ID} for new comments")
    else:
        logger.info("Polling all accessible Notion pages for new comments")
    
    # Step 1: Get all comments from the page/block as a flat list
    all_comments = get_comments_from_page(block_id=NOTION_PAGE_ID)
    
    # Step 2: Filter out already processed comments
    unprocessed_comments = get_unprocessed_comments(all_comments)
    
    if not unprocessed_comments:
        logger.info("No new comments to process")
        return
    
    # Log summary of what we found
    logger.info(f"Found {len(unprocessed_comments)} unprocessed comments to process")
    
    # Process all comments sequentially
    # Each comment will be added to the Discussion Pool during processing
    if unprocessed_comments:
        logger.info(f"Processing {len(unprocessed_comments)} comments sequentially")
        process_comments(unprocessed_comments)
    
    logger.info(f"Finished polling. Total processed comments: {len(processed_comments)}")
    logger.info(f"Discussion Pool now contains {len(discussion_pool.discussions)} parent pages/blocks")

def start_scheduler():
    """Start a simple polling loop at regular intervals."""
    while POLLING_ACTIVE:
        poll_notion_page()
        time.sleep(POLLING_INTERVAL)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "notion_page_id": NOTION_PAGE_ID if NOTION_PAGE_ID else "all pages",
        "processed_comments": len(processed_comments),
        "discussion_pool_size": len(discussion_pool.discussions)
    })

@app.route('/status', methods=['GET'])
def status():
    """Service status and statistics endpoint."""
    return jsonify({
        "status": "running",
        "notion_page_id": NOTION_PAGE_ID if NOTION_PAGE_ID else "all pages",
        "polling_interval": POLLING_INTERVAL,
        "processed_comments": len(processed_comments),
        "discussion_pool_size": len(discussion_pool.discussions)
    })

@app.route('/manual-poll', methods=['GET'])
def manual_poll():
    """Trigger an immediate polling cycle."""
    poll_notion_page()
    return jsonify({
        "status": "success",
        "message": "Manual polling completed",
        "processed_comments": len(processed_comments),
        "discussion_pool_size": len(discussion_pool.discussions)
    })

@app.route('/discussions', methods=['GET'])
def view_discussions():
    """View the entire discussion pool."""
    # Convert the discussion pool to a serializable format
    serializable_pool = {}
    for parent_id, discussions in discussion_pool.discussions.items():
        serializable_pool[parent_id] = {}
        for discussion_id, messages in discussions.items():
            serializable_pool[parent_id][discussion_id] = {}
            for message_id, message in messages.items():
                # Create a simplified version of the message data
                message_data = message["data"]
                text = ""
                if "rich_text" in message_data and len(message_data["rich_text"]) > 0:
                    text = message_data["rich_text"][0].get("text", {}).get("content", "")
                
                serializable_pool[parent_id][discussion_id][message_id] = {
                    "text": text,
                    "status": message["status"],
                    "created_time": message_data.get("created_time", "")
                }
    
    return jsonify({
        "discussion_pool_size": len(discussion_pool.discussions),
        "discussions": serializable_pool
    })

if __name__ == '__main__':
    # Only start the application if all required environment variables are set
    if not missing_vars:
        # Start the polling scheduler in a separate thread
        scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Start the Flask app
        logger.info("Starting Notion Comment Echo Service")
        app.run(host='0.0.0.0', port=PORT, debug=False)
    else:
        logger.error("Application not started due to missing environment variables.")
