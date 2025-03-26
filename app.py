import os
import time
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify
from dotenv import load_dotenv
import openai
from notion_client import Client

# Import database models and services
from models.database import init_db
from models.comment_service import CommentService

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

# Initialize database
init_db(app)

# # Notion API configuration
# NOTION_API_KEY = os.getenv("NOTION_API_KEY")
# NOTION_API_BASE_URL = "https://api.notion.com/v1"
# NOTION_HEADERS = {
#     "Authorization": f"Bearer {NOTION_API_KEY}",
#     "Notion-Version": "2022-06-28",
#     "Content-Type": "application/json"
# }

# Initialize Notion client
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
notion = Client(auth=NOTION_API_KEY)

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Get configuration from environment variables
NOTION_PAGE_ID = os.getenv("NOTION_PAGE")
print("NOTION_PAGE_ID", NOTION_PAGE_ID)
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "60"))  # Default to 60 seconds
PORT = int(os.getenv("PORT", "5001"))  # Default to port 5001
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))

# Check for required environment variables
required_vars = ["NOTION_API_KEY", "NOTION_PAGE", "OPENAI_API_KEY"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these variables in your .env file. See .env.sample for reference.")

# Flag to control polling
POLLING_ACTIVE = True

# Store processed comment IDs to avoid duplicate processing
# Now using database to track processed comments
processed_comments = set()

def get_comments_from_page():
    """Retrieve all comments from the specified Notion page and save to database."""
    try:
        # Get comments from the page using notion-client
        comments = notion.comments.list(block_id=NOTION_PAGE_ID)
        results = comments.get("results", [])
        
        # Save comments to database with comparison logic
        if results:
            result = CommentService.save_comments_to_db(results)
            logger.info(f"Comment processing results: {result['new']} new, {result['updated']} updated, {result['unchanged']} unchanged")
        
        return results
    except Exception as e:
        logger.error(f"Error retrieving comments: {e}")
        return []

def process_comment(comment):
    """Process a single comment with the LLM and post a response."""
    try:
        # Extract comment information
        comment_id = comment["id"]
        comment_text = ""
        if "rich_text" in comment and len(comment["rich_text"]) > 0:
            comment_text = comment["rich_text"][0].get("text", {}).get("content", "")
        
        # Determine parent ID for the reply
        parent_id = None
        if "parent" in comment:
            if "page_id" in comment["parent"]:
                parent_id = comment["parent"]["page_id"]
            elif "block_id" in comment["parent"]:
                parent_id = comment["parent"]["block_id"]
        
        if not parent_id or not comment_text:
            logger.warning(f"Skipping comment {comment_id}: Missing parent_id or comment_text")
            CommentService.mark_comment_as_error(comment_id, "Missing parent_id or comment_text")
            return
        
        # If this is a comment we've already processed, skip it
        if comment_id in processed_comments:
            return
        
        logger.info(f"Processing new comment: {comment_id}")
        logger.info(f"Comment text: {comment_text}")
        
        # Get the thread context if this is a reply
        thread_context = ""
        if "discussion_id" in comment:
            try:
                # Get discussion using notion-client
                discussion = notion.discussions.retrieve(discussion_id=comment['discussion_id'])
                thread_comments = discussion.get("comments", [])
            except Exception as e:
                logger.error(f"Error retrieving discussion thread: {e}")
                thread_context = ""
            else:
                for thread_comment in thread_comments:
                    if thread_comment["id"] != comment_id and "rich_text" in thread_comment:
                        thread_text = thread_comment["rich_text"][0].get("text", {}).get("content", "")
                        if thread_text:
                            thread_context += f"Previous comment: {thread_text}\n"
        
        # Generate response using OpenAI client
        prompt = f"{thread_context}Comment: {comment_text}\n\nPlease provide a helpful response to this comment."
        
        response = openai.ChatCompletion.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant responding to comments in Notion."},
                {"role": "user", "content": prompt}
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS
        )
        
        ai_response = response.choices[0].message.content
        
        # Post the response as a reply
        comment_payload = {
            "parent": {"page_id": parent_id} if "page_id" in comment.get("parent", {}) else {"block_id": parent_id},
            "rich_text": [{
                "type": "text",
                "text": {
                    "content": f"AI Assistant: {ai_response}"
                }
            }]
        }
        
        # Use notion-client to create the comment
        notion.comments.create(**comment_payload)
        
        # Mark this comment as processed in both memory and database
        processed_comments.add(comment_id)
        CommentService.mark_comment_as_processed(comment_id)
        logger.info(f"Successfully responded to comment {comment_id}")
        
    except Exception as e:
        logger.error(f"Error processing comment {comment.get('id', 'unknown')}: {e}")
        CommentService.mark_comment_as_error(comment.get('id', 'unknown'))

def get_comments_from_db(discussion_id=None, parent_id=None, status=None):
    """Retrieve comments from the database with optional filters."""
    return CommentService.get_comments_from_db(discussion_id, parent_id, status)

def poll_notion_page():
    """Poll the Notion page for new comments and process them."""
    if not NOTION_PAGE_ID:
        logger.error("NOTION_PAGE_ID not set in environment variables")
        return
    
    logger.info(f"Polling Notion page {NOTION_PAGE_ID} for new comments")
    
    # Use Flask application context for database operations
    with app.app_context():
        # Get comments from Notion page
        comments = get_comments_from_page()
        
        # Get comments that need processing (new or updated)
        from models.database import Comment
        comments_to_process = Comment.query.filter(Comment.status.in_(['new', 'updated'])).all()
        
        logger.info(f"Found {len(comments_to_process)} comments to process (new or updated)")
        
        # Process each comment that needs processing
        for comment in comments_to_process:
            logger.info(f"Processing comment {comment.id} with status {comment.status}")
            # Convert database comment to format expected by process_comment
            comment_data = {
                "id": comment.id,
                "discussion_id": comment.discussion_id,
                "parent": {
                    f"{comment.parent_type}_id": comment.parent_id
                },
                "rich_text": [{
                    "text": {
                        "content": comment.plain_text
                    }
                }],
                "created_time": comment.created_time.isoformat() if comment.created_time else None,
                "last_edited_time": comment.last_edited_time.isoformat() if comment.last_edited_time else None,
                "created_by": {
                    "id": comment.created_by_id
                } if comment.created_by_id else None
            }
            
            # Process the comment
            process_comment(comment_data)
        
        logger.info(f"Finished polling. Processed {len(processed_comments)} comments in total")

def start_scheduler():
    """Start a simple polling loop at regular intervals."""
    while POLLING_ACTIVE:
        # Each polling cycle runs in the app context
        poll_notion_page()
        time.sleep(POLLING_INTERVAL)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    # Check database connection
    db_healthy = True
    try:
        from models.database import Comment
        Comment.query.limit(1).all()
    except Exception as e:
        db_healthy = False
        logger.error(f"Database health check failed: {e}")
    
    return jsonify({
        "status": "healthy",
        "database": "connected" if db_healthy else "error",
        "timestamp": datetime.now().isoformat(),
        "notion_page_id": NOTION_PAGE_ID,
        "processed_comments": len(processed_comments)
    })

@app.route('/status', methods=['GET'])
def status():
    """Service status and statistics endpoint."""
    # Get comment statistics from database
    from models.database import Comment
    total_comments = Comment.query.count()
    processed_count = Comment.query.filter_by(status='processed').count()
    new_count = Comment.query.filter_by(status='new').count()
    error_count = Comment.query.filter_by(status='error').count()
    
    return jsonify({
        "status": "running",
        "notion_page_id": NOTION_PAGE_ID,
        "polling_interval": POLLING_INTERVAL,
        "llm_model": LLM_MODEL,
        "comments": {
            "total": total_comments,
            "processed": processed_count,
            "new": new_count,
            "error": error_count
        },
        "processed_comments_memory": len(processed_comments),  # Legacy tracking
        "timestamp": datetime.now().isoformat()
    })

@app.route('/manual-poll', methods=['GET'])
def manual_poll():
    """Trigger an immediate polling cycle."""
    poll_notion_page()
    
    # Get updated statistics from database
    from models.database import Comment
    total_comments = Comment.query.count()
    processed_count = Comment.query.filter_by(status='processed').count()
    
    return jsonify({
        "status": "success",
        "message": "Manual polling completed",
        "comments": {
            "total": total_comments,
            "processed": processed_count
        },
        "processed_comments_memory": len(processed_comments),  # Legacy tracking
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Only start the application if all required environment variables are set
    if not missing_vars:
        # Start the polling scheduler in a separate thread
        scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Start the Flask app
        logger.info("Starting Notion Comment AI Assistant")
        app.run(host='0.0.0.0', port=PORT, debug=False)
    else:
        logger.error("Application not started due to missing environment variables.")
