import os
import time
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify
from dotenv import load_dotenv
import requests
import openai

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
NOTION_API_BASE_URL = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Get configuration from environment variables
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "60"))  # Default to 60 seconds
PORT = int(os.getenv("PORT", "5001"))  # Default to port 5001
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))

# Check for required environment variables
required_vars = ["NOTION_API_KEY", "NOTION_PAGE_ID", "OPENAI_API_KEY"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these variables in your .env file. See .env.sample for reference.")

# Flag to control polling
POLLING_ACTIVE = True

# Store processed comment IDs to avoid duplicate processing
processed_comments = set()

def get_comments_from_page():
    """Retrieve all comments from the specified Notion page."""
    try:
        # Get comments from the page using requests
        url = f"{NOTION_API_BASE_URL}/comments?block_id={NOTION_PAGE_ID}"
        response = requests.get(url, headers=NOTION_HEADERS)
        response.raise_for_status()
        return response.json().get("results", [])
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
                url = f"{NOTION_API_BASE_URL}/discussions/{comment['discussion_id']}"
                response = requests.get(url, headers=NOTION_HEADERS)
                response.raise_for_status()
                discussion = response.json()
                thread_comments = discussion.get("comments", [])
            except requests.exceptions.RequestException as e:
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
        
        comment_url = f"{NOTION_API_BASE_URL}/comments"
        comment_response = requests.post(comment_url, headers=NOTION_HEADERS, json=comment_payload)
        comment_response.raise_for_status()
        
        # Mark this comment as processed
        processed_comments.add(comment_id)
        logger.info(f"Successfully responded to comment {comment_id}")
        
    except Exception as e:
        logger.error(f"Error processing comment {comment.get('id', 'unknown')}: {e}")

def poll_notion_page():
    """Poll the Notion page for new comments and process them."""
    if not NOTION_PAGE_ID:
        logger.error("NOTION_PAGE_ID not set in environment variables")
        return
    
    logger.info(f"Polling Notion page {NOTION_PAGE_ID} for new comments")
    comments = get_comments_from_page()
    
    for comment in comments:
        process_comment(comment)
    
    logger.info(f"Finished polling. Processed {len(processed_comments)} comments in total")

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
        "notion_page_id": NOTION_PAGE_ID,
        "processed_comments": len(processed_comments)
    })

@app.route('/status', methods=['GET'])
def status():
    """Service status and statistics endpoint."""
    return jsonify({
        "status": "running",
        "notion_page_id": NOTION_PAGE_ID,
        "polling_interval": POLLING_INTERVAL,
        "llm_model": LLM_MODEL,
        "processed_comments": len(processed_comments),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/manual-poll', methods=['GET'])
def manual_poll():
    """Trigger an immediate polling cycle."""
    poll_notion_page()
    return jsonify({
        "status": "success",
        "message": "Manual polling completed",
        "processed_comments": len(processed_comments),
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
