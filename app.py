import os
import time
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify
from dotenv import load_dotenv
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

# Initialize Notion client
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
notion = Client(auth=NOTION_API_KEY)

# Get configuration from environment variables
NOTION_PAGE_ID = os.getenv("NOTION_PAGE")
print("NOTION_PAGE_ID", NOTION_PAGE_ID)
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "60"))  # Default to 60 seconds
PORT = int(os.getenv("PORT", "5001"))  # Default to port 5001

# Check for required environment variables
required_vars = ["NOTION_API_KEY", "NOTION_PAGE"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these variables in your .env file. See .env.sample for reference.")

# Flag to control polling
POLLING_ACTIVE = True

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



def get_comments_from_db(discussion_id=None, parent_id=None, status=None):
    """Retrieve comments from the database with optional filters."""
    return CommentService.get_comments_from_db(discussion_id, parent_id, status)

def poll_notion_page():
    """Poll the Notion page for new comments."""
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
        
        if comments_to_process:
            logger.info(f"Found {len(comments_to_process)} comments to process (new or updated)")
            # Just log the comments, no processing
            for comment in comments_to_process:
                logger.info(f"New comment detected: {comment.id} - {comment.plain_text[:50]}...")
        else:
            logger.info("No new comments to process")
        
        logger.info("Finished polling cycle")

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
        "notion_page_id": NOTION_PAGE_ID
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
        "comments": {
            "total": total_comments,
            "processed": processed_count,
            "new": new_count,
            "error": error_count
        },
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
    new_count = Comment.query.filter_by(status='new').count()
    
    return jsonify({
        "status": "success",
        "message": "Manual polling completed",
        "comments": {
            "total": total_comments,
            "processed": processed_count,
            "new": new_count
        },
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
