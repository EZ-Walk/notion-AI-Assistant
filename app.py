import os
import time
import logging
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from flask import Flask, jsonify
from dotenv import load_dotenv
from openai import OpenAI
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

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

# Initialize OpenAI client with v2 Assistants API header
openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
    default_headers={"OpenAI-Beta": "assistants=v2"}
)

# Get configuration from environment variables
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "60"))  # Default to 60 seconds
PORT = int(os.getenv("PORT", "5001"))  # Default to port 5001
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))

# Check for required environment variables
required_vars = ["NOTION_API_KEY", "NOTION_PAGE_ID", "OPENAI_API_KEY", "ASSISTANT_ID"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these variables in your .env file. See .env.sample for reference.")

# Flag to control polling
POLLING_ACTIVE = True

# Store processed comment IDs to avoid duplicate processing
processed_comments = set()

def get_comments_from_page():
    """Retrieve all open (un-resolved) comments from the specified Notion page or block.
    
    According to Notion API docs, this endpoint returns a flatlist of comments associated 
    with the ID provided. Multiple discussion threads may be included in the response,
    with comments from all threads returned in ascending chronological order.
    """
    try:
        # Get comments from the page using the Notion SDK
        response = notion.comments.list(block_id=NOTION_PAGE_ID)
        
        # Return the results, which is a flatlist of comments
        comments = response.get("results", [])
        logger.info(f"Retrieved {len(comments)} comments from Notion page/block")
        return comments
    except Exception as e:
        logger.error(f"Error retrieving comments: {e}")
        return []

def process_comment(comment):
    """Synchronous wrapper for process_comment_async.
    
    This function exists for backward compatibility and to provide a synchronous
    interface to the asynchronous comment processing function.
    """
    # Create a new event loop for this thread if one doesn't exist
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Run the async function in the event loop
    return loop.run_until_complete(process_comment_async(comment))

async def process_comment_async(comment):
    """Process a single comment with the OpenAI Assistants API and post a response asynchronously.
    
    Handles comments from different discussion threads by organizing thread context
    based on the discussion_id field. Uses the Assistants API thread model to maintain
    conversation context.
    
    Note: This function assumes the comment has not been processed before. The caller
    should check the processed_comments set before calling this function.
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
        
        # Note: Skipping already processed comments is now handled by get_unprocessed_comments()
        # so we don't need to check here, but we'll log it for debugging purposes
        logger.debug(f"Processing comment: {comment_id}")
        
        logger.info(f"Processing new comment: {comment_id} from discussion: {discussion_id}")
        logger.info(f"Comment text: {comment_text}")
        
        # Create or retrieve a thread for this discussion
        # Use the discussion_id as the external_id for the thread to maintain continuity
        thread_id = None
        
        # If this is part of an existing discussion, check if we have a thread for it
        if discussion_id:
            # Try to find an existing thread with this discussion_id
            try:
                # List threads with the metadata filter for this discussion_id
                threads = openai_client.beta.threads.list()
                for thread in threads.data:
                    # Check if this thread is for our discussion
                    if getattr(thread, 'metadata', {}).get('discussion_id') == discussion_id:
                        thread_id = thread.id
                        logger.info(f"Found existing thread {thread_id} for discussion {discussion_id}")
                        break
            except Exception as e:
                logger.error(f"Error finding existing thread: {e}")
        
        # If no thread found or this is a new discussion, create a new thread
        if not thread_id:
            try:
                # Create a new thread with metadata to track the discussion_id
                metadata = {}
                if discussion_id:
                    metadata['discussion_id'] = discussion_id
                
                thread = openai_client.beta.threads.create(metadata=metadata)
                thread_id = thread.id
                logger.info(f"Created new thread {thread_id} for discussion {discussion_id if discussion_id else 'new'}")
            except Exception as e:
                logger.error(f"Error creating thread: {e}")
                raise
        
        # Add the user message to the thread
        try:
            message = openai_client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=comment_text
            )
            logger.info(f"Added message to thread {thread_id}")
        except Exception as e:
            logger.error(f"Error adding message to thread: {e}")
            raise
        
        # Run the assistant on the thread
        try:
            run = openai_client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=ASSISTANT_ID,
                instructions="You are responding to comments in a Notion document. Be helpful, concise, and friendly."
            )
            logger.info(f"Started run {run.id} on thread {thread_id}")
        except Exception as e:
            logger.error(f"Error starting run: {e}")
            raise
        
        # Wait for the run to complete - using async sleep instead of blocking
        while True:
            try:
                run_status = openai_client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )
                if run_status.status == 'completed':
                    logger.info(f"Run {run.id} completed")
                    break
                elif run_status.status in ['failed', 'cancelled', 'expired']:
                    logger.error(f"Run {run.id} ended with status {run_status.status}")
                    raise Exception(f"Run ended with status {run_status.status}")
                else:
                    logger.info(f"Run {run.id} status: {run_status.status}")
                    await asyncio.sleep(1)  # Async wait before checking again
            except Exception as e:
                logger.error(f"Error checking run status: {e}")
                raise
        
        # Get the assistant's response
        try:
            messages = openai_client.beta.threads.messages.list(
                thread_id=thread_id
            )
            
            # Get the most recent assistant message
            assistant_messages = [msg for msg in messages.data if msg.role == 'assistant']
            if not assistant_messages:
                raise Exception("No assistant response found")
            
            # Get the most recent message (first in the list)
            latest_message = assistant_messages[0]
            ai_response = latest_message.content[0].text.value
            logger.info(f"Got assistant response: {ai_response[:100]}...")
        except Exception as e:
            logger.error(f"Error getting assistant response: {e}")
            raise
        
        # Post the response as a reply using the Notion SDK
        rich_text = [{
            "type": "text",
            "text": {
                "content": f"AI Assistant: {ai_response}"
            }
        }]
        
        try:
            # Based on the successful approach from our testing, use the simplified method
            # that works with the Notion SDK
            parent_dict = {}
            
            # Set either page_id or block_id, but not both
            if "page_id" in comment.get("parent", {}):
                parent_dict = {"page_id": parent_id}
                logger.info(f"Creating comment on page {parent_id}")
            else:
                parent_dict = {"block_id": parent_id}
                logger.info(f"Creating comment on block {parent_id}")
            
            # Create the comment with the appropriate parameters
            if discussion_id:
                logger.info(f"This is a reply in discussion {discussion_id}")
            
            # Create the comment using the simplified approach that worked in testing
            notion.comments.create(
                parent=parent_dict,
                rich_text=rich_text
            )
            logger.info("Comment created successfully")
            
        except Exception as e:
            logger.error(f"Error creating comment: {e}")
            # Try with discussion_id if the first attempt failed and we have a discussion_id
            if discussion_id:
                try:
                    logger.info(f"Trying again with discussion_id parameter")
                    parent_dict = {}
                    if "page_id" in comment.get("parent", {}):
                        parent_dict = {"page_id": parent_id}
                    else:
                        parent_dict = {"block_id": parent_id}
                        
                    notion.comments.create(
                        parent=parent_dict,
                        discussion_id=discussion_id,
                        rich_text=rich_text
                    )
                    logger.info("Comment created with discussion_id parameter")
                except Exception as e2:
                    logger.error(f"Second attempt to create comment failed: {e2}")
                    raise
            else:
                # If there's no discussion_id and the first attempt failed, re-raise the exception
                raise
        
        # Mark this comment as processed
        processed_comments.add(comment_id)
        logger.info(f"Successfully responded to comment {comment_id}")
        
    except Exception as e:
        logger.error(f"Error processing comment {comment.get('id', 'unknown')}: {e}")

def get_discussion_context(discussion_id, current_comment_id):
    """Retrieve the context of a discussion thread.
    
    Args:
        discussion_id: The ID of the discussion thread
        current_comment_id: The ID of the current comment being processed
        
    Returns:
        A string containing the context of previous comments in the thread
    """
    thread_context = ""
    try:
        # Get all comments in the discussion thread using the Notion SDK
        # The Notion SDK doesn't directly support filtering by discussion_id in the list method
        # So we'll get all comments and filter them manually
        response = notion.comments.list(block_id=NOTION_PAGE_ID)
        all_comments = response.get("results", [])
        
        # Filter comments by discussion_id
        thread_comments = [c for c in all_comments if c.get("discussion_id") == discussion_id]
        
        # Sort comments by created_time to ensure chronological order
        thread_comments.sort(key=lambda x: x.get("created_time", ""))
        
        # Build context from previous comments in the thread
        for thread_comment in thread_comments:
            # Skip the current comment and comments without text
            if thread_comment["id"] == current_comment_id or "rich_text" not in thread_comment:
                continue
                
            # Skip comments that don't have text content
            if not thread_comment["rich_text"] or len(thread_comment["rich_text"]) == 0:
                continue
                
            # Extract the text content
            thread_text = thread_comment["rich_text"][0].get("text", {}).get("content", "")
            if thread_text:
                # Add the comment to the context
                author = thread_comment.get("created_by", {}).get("name", "Unknown")
                thread_context += f"Previous comment by {author}: {thread_text}\n"
                
        return thread_context
    except Exception as e:
        logger.error(f"Error retrieving discussion thread {discussion_id}: {e}")
        return ""

def organize_comments_by_thread(comments):
    """Organize comments by their discussion threads.
    
    Args:
        comments: A list of comments from the Notion API
        
    Returns:
        A dictionary mapping discussion_ids to lists of comments
    """
    # This function is kept for backward compatibility but now uses the more detailed function
    threads = {}
    organized = organize_comments_by_parent_and_thread(comments)
    
    # Flatten the parent structure to just get discussion threads
    for parent_threads in organized.values():
        for discussion_id, thread_comments in parent_threads.items():
            if discussion_id not in threads:
                threads[discussion_id] = []
            threads[discussion_id].extend(thread_comments)
    
    return threads

def get_unprocessed_comments(comments):
    """Filter out already processed comments.
    
    Args:
        comments: A list of comments from the Notion API
        
    Returns:
        A list of comments that haven't been processed yet
    """
    unprocessed = []
    
    for comment in comments:
        comment_id = comment.get("id")
        if comment_id and comment_id not in processed_comments:
            unprocessed.append(comment)
    
    logger.info(f"Found {len(unprocessed)} unprocessed comments out of {len(comments)} total comments")
    return unprocessed

def organize_comments_by_parent_and_thread(comments):
    """Organize comments by their parent page/block and discussion threads.
    
    Args:
        comments: A list of comments from the Notion API
        
    Returns:
        A dictionary mapping parent_ids to dictionaries of discussion_ids to lists of comments
    """
    organized = {}
    
    for comment in comments:
        # Determine parent ID for the reply (could be page_id or block_id)
        parent_id = None
        if "parent" in comment:
            if "page_id" in comment["parent"]:
                parent_id = comment["parent"]["page_id"]
            elif "block_id" in comment["parent"]:
                parent_id = comment["parent"]["block_id"]
        
        # Skip if no parent_id found
        if not parent_id:
            logger.warning(f"Skipping comment {comment.get('id', 'unknown')}: Missing parent_id")
            continue
        
        # Get discussion ID, default to "unthreaded" if not present
        discussion_id = comment.get("discussion_id", "unthreaded")
        
        # Initialize nested dictionaries if needed
        if parent_id not in organized:
            organized[parent_id] = {}
        if discussion_id not in organized[parent_id]:
            organized[parent_id][discussion_id] = []
        
        # Add comment to the appropriate list
        organized[parent_id][discussion_id].append(comment)
    
    # Sort comments within each thread by created_time
    for parent_id in organized:
        for discussion_id in organized[parent_id]:
            organized[parent_id][discussion_id] = sorted(
                organized[parent_id][discussion_id], 
                key=lambda x: x.get("created_time", "")
            )
    
    return organized

async def process_comments_async(comments):
    """Process a list of comments asynchronously.
    
    Args:
        comments: A list of comments to process
    """
    # Create tasks for each comment
    tasks = [process_comment_async(comment) for comment in comments]
    
    # Process all comments concurrently and wait for them to complete
    await asyncio.gather(*tasks)

def poll_notion_page():
    """Poll the Notion page for new comments and process them.
    
    Retrieves all open (un-resolved) comments from the specified Notion page or block,
    organizes them by parent page/block and discussion thread, filters out already 
    processed comments, and processes each unprocessed comment asynchronously.
    """
    if not NOTION_PAGE_ID:
        logger.error("NOTION_PAGE_ID not set in environment variables")
        return
    
    logger.info(f"Polling Notion page {NOTION_PAGE_ID} for new comments")
    
    # Step 1: Get all comments from the page/block as a flat list
    all_comments = get_comments_from_page()
    
    # Step 2: Filter out already processed comments
    unprocessed_comments = get_unprocessed_comments(all_comments)
    
    if not unprocessed_comments:
        logger.info("No new comments to process")
        return
    
    # Step 3: Organize unprocessed comments by parent page/block and discussion thread
    organized_comments = organize_comments_by_parent_and_thread(unprocessed_comments)
    
    # Log summary of what we found
    parent_count = len(organized_comments)
    thread_count = sum(len(threads) for threads in organized_comments.values())
    logger.info(f"Found {thread_count} discussion threads across {parent_count} parent pages/blocks")
    
    # Step 4: Process each unprocessed comment asynchronously
    # Flatten the organized comments into a single list
    all_unprocessed = []
    for parent_id, threads in organized_comments.items():
        logger.info(f"Processing comments for parent {parent_id}")
        for discussion_id, comments in threads.items():
            logger.info(f"Processing thread {discussion_id} with {len(comments)} comments")
            all_unprocessed.extend(comments)
    
    # Create a new event loop for this thread if one doesn't exist
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Process all comments asynchronously
    if all_unprocessed:
        logger.info(f"Processing {len(all_unprocessed)} comments asynchronously")
        loop.run_until_complete(process_comments_async(all_unprocessed))
    
    logger.info(f"Finished polling. Total processed comments: {len(processed_comments)}")

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
        "assistant_id": ASSISTANT_ID,
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
