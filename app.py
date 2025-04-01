import os
import time
import logging
import threading
from typing import Optional
from datetime import datetime
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from notion_client import Client

# Import database models and services
from models.database import init_db
from models.comment_service import CommentService
# Import LangGraph agent
from models.langgraph_agent import get_graph

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

# Initialize the agent for processing comments
# notion_agent = create_custom_notion_agent()
notion_agent = get_graph()

# Get configuration from environment variables
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "60"))  # Default to 60 seconds
PORT = int(os.getenv("PORT", "5001"))  # Default to port 5001

# Check for required environment variables
required_vars = ["NOTION_API_KEY", "NOTION_PAGE"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these variables in your .env file. See .env.sample for reference.")

# Flag to control polling
POLLING_ACTIVE = False

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

def fetch_comment_from_parent(parent_id: str, comment_id: Optional[str] = None):
	comments = notion.comments.list(block_id=parent_id)
 
	# catch no comments found by checking the length of the results field
	if len(comments.get('results', [])) == 0:
		return {}

	# optionally, return only the comment requested by ID
	if comment_id:
		for this_c in comments.get('results'):
			if this_c['id'] == comment_id:
				return this_c

	# Finally, return all comments
	return comments.get('results', 'No comments found')

def process_comment(request_json):
    """Handle Notion comment events."""
    
    # Get comments on the parent block
    comment = fetch_comment_from_parent(request_json['data']['parent']['id'], request_json['entity']['id'])
    # logger.info(f"Comment data: {comment}")
    
    # Extract the comment's text
    try:
        comment_text = [item['plain_text'] for item in comment['rich_text']]
        logger.info(f"Comment text: {comment_text}")
    except Exception as e:
        logger.error(f"Failed to extract comment text: {e}")
        return
    
    # Process the comment using the agent
    response = notion_agent.invoke({"messages": [{"role": "user", "content": comment_text}]})
    logger.info(f"Agent Response: {response}")
    
    # Reply to the triggering comment with the response
    reply = notion.comments.create(discussion_id=comment['discussion_id'], 
                        rich_text=[{
                                    "text": {
                                    "content": response['messages'][-1].content
                                    }
                                }]
    )
    
    return reply 
    
def action_router(event_payload):
    """Route the event payload to the appropriate handler based on event type and content.
    
    Args:
        event_payload (dict): The JSON payload from the webhook event
        
    Returns:
        dict: Response data with status and any additional information
    """
    logging.info(f"Routing action for event: {event_payload.get('type', 'unknown')}") 
    print(event_payload)
    
    response = {"status": "success", "action": "none"}
    
    # Check if the author is a person (not a bot)
    if event_payload.get('authors') and event_payload['authors'][0].get('type') == 'person':
        logging.info(f"Processing comment from person: {event_payload['authors'][0].get('id', 'unknown')}") 
        
        # Process the comment with the additional context
        if event_payload.get('type') == 'comment.created':
            result = process_comment(event_payload)
            
            response.update({
                "action": "processed_comment",
                "result": result
        })
        elif event_payload.get('type') == 'comment.deleted':
            pass
            # TODO: Handle comment deletion
            
    else:
        logging.info("Skipping event: not from a person or no author information")
    
    return response


@app.route('/comment-created', methods=['POST'])
def handle_comment_created():
    """Handle Notion comment events."""
    
    # Handle a webhook verification request
    if request.json.get('verification_token'):
        logging.info(f"Received verification token: {request.json['verification_token']}")
        return jsonify({"status": "success"})
    
    # Handle a new comment event
    logging.info(f"New {request.json.get('type', 'unknown')} event received")
    # Route the event to the appropriate handler
    response = action_router(request.json)
    
    return jsonify(response)

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
        if POLLING_ACTIVE:
            scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
            scheduler_thread.start()
        
        # Start the Flask app
        logger.info("Starting Notion Comment AI Assistant")
        app.run(host='0.0.0.0', port=PORT, debug=True)
    else:
        logger.error("Application not started due to missing environment variables.")
