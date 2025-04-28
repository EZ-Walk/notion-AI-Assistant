import os
import logging
from typing import Optional
from datetime import datetime
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from notion_client import Client

# Import Supabase database and services
from models.supabase_db import get_subscriptions, is_user_authorized, get_supabase_client

# Import LangGraph agent
from models.agent import graph, LLM_MODEL, LLM_TEMPERATURE


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

# Initialize Supabase client
supabase = get_supabase_client()
if not supabase:
    logger.error("Failed to create Supabase admin client")
    exit(1)
logger.info("Supabase admin client initialized successfully")


# Get configuration from environment variables
PORT = int(os.getenv("PORT", "5001"))  # Default to port 5001

# Check for required environment variables

required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "ANTHROPIC_API_KEY"]

missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these variables in your .env file. See .env.sample for reference.")


def get_comments_from_notion():
    """Retrieve all comments from the specified Notion page and save to database."""
    try:
        # Get comments from the page using notion-client
        comments = notion.comments.list()
        results = comments.get("results", [])
                
        return results

    except Exception as e:
        logger.error(f"Error retrieving comments: {e}")
        return []


def fetch_comment_from_parent(comments: dict, parent_id: str, comment_id: Optional[str] = None):
    """
    Sort comments returned by the notion API by returning a list of ordered comments belonging to the block with the given parent_id.
    Optionally, return only the comment requested by ID.
    
    Args:
        comments (dict): Dictionary of comments retrieved from Notion
        parent_id (str): ID of the parent block
        comment_id (str, optional): ID of the specific comment to fetch
        
    Returns:
        dict: Dictionary of comments or a specific comment if comment_id is provided
    """
 
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
    logger.info(f"Processing comment event: {request_json.get('id', 'unknown')}")
    
    # Use the global supabase client with admin access
    # Get the user's access token from the subscriptions table
    try:
        response = supabase.table("subscriptions").select("access_token").eq("notion_user_id", request_json['authors'][0]['id']).execute()
        
        if not response.data:
            logger.error(f"No subscription found for Notion user ID: {request_json['authors'][0]['id']}")
            return {"status": "error", "message": "No subscription found"}
            
        access_token = response.data[0].get('access_token')
        
        if not access_token:
            logger.error(f"No access token found for Notion user ID: {request_json['authors'][0]['id']}")
            return {"status": "error", "message": "No access token found"}
        
        # Initialize Notion client with user's access token
        notion = Client(auth=access_token)
        
        # Get comments on the parent block
        comments = notion.comments.list(block_id=request_json['data']['parent']['id'])
        
        comment = fetch_comment_from_parent(comments, request_json['data']['parent']['id'], request_json['entity']['id'])
        logger.info(f"Comment data: {comment}")
        
        # Extract the comment's text
        try:
            comment_text = [item['plain_text'] for item in comment['rich_text']]
            logger.info(f"Comment text: {comment_text}")
        except Exception as e:
            logger.error(f"Failed to extract comment text: {e}")
            return {"status": "error", "message": f"Failed to extract comment text: {e}"}
        
        # Process the comment using the agent
        response = graph.invoke(
            {"messages": [{"role": "user", "content": comment_text}]},
            config={'configurable': {'thread_id': comment['discussion_id']}}
        )
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
    except Exception as e:
        logger.error(f"Error processing comment: {e}")
        return {"status": "error", "message": f"Error processing comment: {e}"}


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


@app.route('/events', methods=['POST'])
def handle_events():
    """Handle Notion comment events."""
    
    # Handle a webhook verification request
    if request.json.get('verification_token'):
        os.environ["NOTION_VERIFICATION_TOKEN"] = request.json['verification_token']
        logging.info(f"Received verification token: {os.environ['NOTION_VERIFICATION_TOKEN']}")
        return jsonify({"status": "success"}), 200
    
    # TODO: validate the request using the verification token set in the environment
    
    if not request.json.get('type'):
        return jsonify({"status": "error", "message": "Invalid event type"}), 200
    
    # Route the event to the appropriate handler
    response = action_router(request.json)
    
    return jsonify(response), 200


@app.route('/', methods=['GET'])
def status():
    """Service status and statistics endpoint."""
    
    # Get subscriptions
    subscriptions = get_subscriptions()
    
    return jsonify({
        "status": "running",
        "LLM_model": LLM_MODEL,
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "subscriptions": {
            "total": len(subscriptions)
        },
        "timestamp": datetime.now().isoformat()
    }), 200


if __name__ == '__main__':
    # Only start the application if all required environment variables are set
    if not missing_vars:
        # Check if Supabase was initialized successfully
        if not supabase:
            logger.error("Failed to initialize Supabase client. Check your credentials.")
        else:
            # Check subscriptions on startup
            subscriptions = get_subscriptions()
            logger.info(f"Found {len(subscriptions)} subscriptions in the database")
            
            # Start the Flask app
            logger.info("Starting Notion Comment AI Assistant")
            app.run(host='0.0.0.0', port=PORT, debug=True)
    else:
        logger.error("Application not started due to missing environment variables.")
