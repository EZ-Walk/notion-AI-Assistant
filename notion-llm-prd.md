# Product Requirements Document: Notion Comment AI Assistant

## 1. Introduction

### 1.1 Purpose
The Notion Comment AI Assistant is a Flask-based web application designed to monitor Notion pages for new comments, process these comments using a Large Language Model (LLM), and automatically respond in the same comment thread with relevant information or assistance.

### 1.2 Product Overview
This application bridges Notion's collaborative workspace with AI capabilities, enabling automated responses to user queries or comments without requiring users to leave the Notion environment. It serves as an embedded AI assistant that works within existing Notion workflows. The application features a simple, user-friendly web interface for account management, Notion integration setup, and monitoring configuration.

### 1.3 Scope
- In-scope: User authentication, Notion public integration setup, monitoring Notion pages, processing comments with an LLM, posting responses
- Out-of-scope: Content creation, document editing, database management in Notion

## 2. Product Features

### 2.1 Core Features

#### 2.1.1 User Authentication & Onboarding
- User registration and login functionality
- Guided Notion integration setup process
- OAuth-based Notion authorization flow
- Simple dashboard for managing monitored pages

#### 2.1.2 Notion Integration
- Utilize Notion's public integration API
- Poll specified Notion pages at regular intervals to check for new comments
- Authenticate with Notion API using OAuth tokens
- Differentiate between previously processed and new comments
- Extract comment text, metadata, and thread context

#### 2.1.3 LLM Processing
- Send comment text as a query to a configured LLM API
- Include relevant context from the comment thread in the LLM prompt
- Process LLM response for appropriate formatting
- Handle rate limiting and API errors gracefully

#### 2.1.4 Response Posting
- Post LLM-generated responses as replies in the original comment thread
- Maintain appropriate attribution (e.g., "AI Assistant:")
- Handle Unicode characters and markdown formatting correctly

### 2.2 Administration Features

#### 2.2.1 Configuration Management
- Configure which Notion pages to monitor
- Set polling frequency
- Specify LLM model parameters (temperature, max tokens, etc.)
- Configure authentication credentials securely

#### 2.2.2 Monitoring and Logging
- Log all activities including comment detection, LLM queries, and responses
- Track error rates and response times
- Provide basic usage statistics

## 3. Technical Requirements

### 3.1 Development Requirements

#### 3.1.1 Technology Stack
- Backend: Flask (Python web framework)
- Frontend: Simple responsive UI using HTML, CSS, and JavaScript (with Bootstrap or similar framework)
- Database: SQLite for development, PostgreSQL for production
- API Integrations: Notion public integration API, LLM provider API (e.g., OpenAI, Anthropic)
- Hosting: Docker container compatible with cloud hosting services
- Authentication: User authentication system with session management and OAuth for Notion integration

#### 3.1.2 API Requirements
- Notion Public Integration API: OAuth-based integration for comment retrieval and posting
- LLM API: Integration for processing comment text and generating responses
- User Authentication API: Secure login and registration system
- Error handling for all APIs with appropriate retry mechanisms

### 3.2 Security Requirements
- Secure user authentication system with password hashing
- Secure storage of OAuth tokens and API keys
- HTTPS implementation with valid SSL certificate
- CSRF protection on all forms
- No storage of actual comment content beyond processing
- Rate limiting to prevent abuse
- Input validation and sanitization
- Secure session management

### 3.3 Performance Requirements
- Response time: < 30 seconds from comment posting to AI response
- Scalability: Support for monitoring multiple pages simultaneously
- Reliability: 99.5% uptime
- Resource efficiency: Minimal CPU and memory footprint

## 4. User Experience

### 4.1 Target Users
- Notion workspace administrators
- Team members using Notion for collaboration
- Support staff responding to internal or external queries

### 4.2 User Interaction Flow
1. User creates an account on the application
2. User completes the Notion integration setup via OAuth authorization flow
3. User selects which Notion pages/workspaces to monitor through a simple dashboard
4. End users post comments on monitored Notion pages
5. Application detects new comments during polling cycles
6. Comment text is processed by the LLM
7. AI response is posted as a reply in the same thread
8. Users continue the conversation naturally, with AI responding as needed
9. Admin user can review activity and adjust settings through dashboard

## 5. Implementation Plan

### 5.1 Development Phases

#### 5.1.1 Phase 1: Core Functionality
- Set up Flask application structure with user authentication
- Create basic frontend with registration, login, and dashboard views
- Implement Notion public integration with OAuth flow
- Develop UI for connecting and selecting Notion workspaces/pages
- Implement Notion API integration for comment polling
- Develop comment processing logic
- Integrate basic LLM functionality
- Implement response posting

#### 5.1.2 Phase 2: Refinements
- Add configuration management
- Improve error handling and logging
- Enhance LLM prompt engineering for better responses
- Add rate limiting and throttling

#### 5.1.3 Phase 3: Production Readiness
- Implement comprehensive testing
- Set up deployment pipeline
- Create documentation
- Add monitoring and alerting

### 5.2 Milestones
1. Proof of concept with basic Notion polling and LLM response
2. Full integration with threaded comments
3. Configuration and management interface
4. Production deployment

## 6. Technical Architecture

### 6.1 Component Diagram
- Flask Web Server
  - Frontend Layer
    - User Authentication Views
    - Dashboard Views
    - Notion Integration Setup Views
    - Configuration Interface
  - Backend Layer
    - User Authentication Service
    - Notion OAuth Service
    - Notion Poller Service
    - Comment Processor
    - LLM Integration Service
    - Response Generator
    - Database Interface
    - Configuration Manager

### 6.2 Database Schema
- Users table: User accounts and authentication details
- NotionIntegrations table: User's Notion OAuth tokens and connection details
- Pages table: Tracked Notion pages linked to user accounts
- Comments table: Processed comment IDs and metadata
- Config table: Application and user-specific settings
- Logs table: Activity and error logs

### 6.3 API Endpoints
#### Frontend Routes
- `/`: Home/landing page
- `/register`: User registration
- `/login`: User login
- `/dashboard`: User dashboard
- `/setup-notion`: Notion integration setup
- `/manage-pages`: Page monitoring management
- `/settings`: User settings

#### Backend API Endpoints
- `/api/health`: Health check endpoint
- `/api/config`: Configuration management
- `/api/status`: Service status and statistics
- `/api/manual-poll`: Trigger an immediate polling cycle
- `/api/notion/callback`: OAuth callback for Notion integration
- `/api/notion/workspaces`: List available Notion workspaces
- `/api/notion/pages`: List available Notion pages

## 7. Testing Requirements

### 7.1 Unit Testing
- Test individual components with mocked dependencies
- Ensure proper error handling
- Validate data processing logic

### 7.2 Integration Testing
- Test Notion API integration with test pages
- Verify LLM integration with controlled prompts
- Validate end-to-end comment processing workflow

### 7.3 Performance Testing
- Test polling efficiency with multiple pages
- Benchmark response times
- Validate resource usage

## 8. Deployment and Operations

### 8.1 Deployment Requirements
- Docker container deployment
- Environment variable configuration
- Database migration support
- Backup and restore procedures

### 8.2 Monitoring Requirements
- Application logs
- API response metrics
- Error rate tracking
- Usage statistics

### 8.3 Maintenance Procedures
- Regular dependency updates
- Database maintenance
- Log rotation and cleanup

## 9. Future Enhancements

### 9.1 Potential Features
- Support for document content context beyond comments
- Integration with additional LLM providers
- Custom response templates
- User feedback mechanism for AI responses
- Advanced analytics on usage patterns

## 10. Implementation Notes

### A.4 User Authentication
```python
from flask import Flask, request, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.secret_key = os.urandom(24)
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered')
            return redirect(url_for('register'))
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    # Get user's Notion integrations
    notion_integrations = get_user_notion_integrations(session['user_id'])
    
    return render_template('dashboard.html', user=user, integrations=notion_integrations)
```

## 10. Implementation Notes

### 10.1 Notion Public Integration Considerations
- Notion public integration requires application registration in the Notion developer portal
- OAuth flow must be implemented for user authorization
- The integration requires specific scopes for comment access and posting
- The Notion API requires a specific format for retrieving and posting comments
- Comment threads are organized hierarchically
- API rate limits must be respected
- Users must be guided through the integration permissions process

### 10.2 LLM Integration Notes
- Prompt engineering is critical for quality responses
- Context window limitations may require chunking or summarization
- Cost considerations based on token usage

## Appendix A: Code Samples

### A.1 Notion OAuth Integration
```python
from flask import Flask, redirect, request, session, url_for
import requests
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

NOTION_CLIENT_ID = os.environ.get("NOTION_CLIENT_ID")
NOTION_CLIENT_SECRET = os.environ.get("NOTION_CLIENT_SECRET")
REDIRECT_URI = "https://yourdomain.com/api/notion/callback"

@app.route('/setup-notion')
def setup_notion():
    """Initiate Notion OAuth flow."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    auth_url = f"https://api.notion.com/v1/oauth/authorize?client_id={NOTION_CLIENT_ID}&response_type=code&owner=user&redirect_uri={REDIRECT_URI}"
    return redirect(auth_url)

@app.route('/api/notion/callback')
def notion_callback():
    """Handle Notion OAuth callback."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    code = request.args.get('code')
    
    # Exchange code for access token
    token_response = requests.post(
        "https://api.notion.com/v1/oauth/token",
        headers={"Content-Type": "application/json"},
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": NOTION_CLIENT_ID,
            "client_secret": NOTION_CLIENT_SECRET
        }
    )
    
    token_data = token_response.json()
    
    # Store the tokens in database
    user_id = session['user_id']
    save_notion_token(user_id, token_data['access_token'], token_data.get('workspace_id'))
    
    return redirect(url_for('dashboard', message="Notion successfully connected!"))
```

### A.2 Notion Comment Polling
```python
def poll_notion_for_comments(user_id, page_id, last_processed_time):
    """
    Poll a Notion page for new comments since the last processed time.
    
    Args:
        user_id: The ID of the user who owns the integration
        page_id: The ID of the Notion page to poll
        last_processed_time: Timestamp of the last processed comment
        
    Returns:
        List of new comments
    """
    # Get user's Notion access token
    user_token = get_user_notion_token(user_id)
    
    if not user_token:
        logger.error(f"No valid Notion token for user {user_id}")
        return []
    
    # Use token to access Notion API
    comments = retrieve_comments(
        pageId=page_id,
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    # Filter for new comments only
    new_comments = [
        comment for comment in comments 
        if comment['created_time'] > last_processed_time
    ]
    
    return new_comments
```

### A.2 LLM Processing
```python
def process_comment_with_llm(comment_text, thread_context):
    """
    Process a comment with the LLM and generate a response.
    
    Args:
        comment_text: The text of the comment to process
        thread_context: Additional context from the comment thread
        
    Returns:
        Generated response text
    """
    # Construct prompt with context
    prompt = f"Comment: {comment_text}\nContext: {thread_context}\n\nPlease provide a helpful response:"
    
    # Call LLM API (example using Anthropic)
    response = anthropic.completions.create(
        model="claude-3-sonnet-20240229",
        prompt=prompt,
        max_tokens_to_sample=1000,
        temperature=0.7
    )
    
    return response.completion
```

### A.3 Response Posting
```python
def post_response_to_thread(user_id, page_id, comment_id, response_text):
    """
    Post a response to a Notion comment thread.
    
    Args:
        user_id: The ID of the user who owns the integration
        page_id: The ID of the Notion page
        comment_id: The ID of the comment to respond to
        response_text: The text of the response
        
    Returns:
        Response metadata from Notion API
    """
    # Get user's Notion access token
    user_token = get_user_notion_token(user_id)
    
    if not user_token:
        logger.error(f"No valid Notion token for user {user_id}")
        return None
    
    # Use token to access Notion API
    response = add_comment(
        pageId=page_id,
        content=f"AI Assistant: {response_text}",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    return response
```
