# Notion Comment Echo Service

A Flask-based application that monitors Notion pages for new comments and automatically responds with an echo of the original comment text.

## Overview

The Notion Comment Echo Service is designed to poll Notion workspaces for new comments, process them, and automatically reply with an echo of the original comment. This application demonstrates the foundation for building an AI-powered comment assistant for Notion.

## Features

- **Notion API Integration**: Polls Notion pages for new comments at regular intervals
- **Comment Processing**: Identifies and processes new comments, avoiding duplicate processing
- **Automated Responses**: Replies to comments with an echo of the original text
- **Thread Context Awareness**: Organizes comments by their discussion threads
- **RESTful Endpoints**: Provides health check, status monitoring, and manual polling capabilities

## Requirements

- Python 3.6+
- Notion API Key
- Optional: Notion Page ID (if you want to limit monitoring to a specific page)

## Installation

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.sample` to `.env` and configure your environment variables:
   ```
   cp .env.sample .env
   ```
5. Edit the `.env` file with your Notion API key and other settings

## Configuration

The application requires the following environment variables:

- `NOTION_API_KEY`: Your Notion API integration token
- `NOTION_PAGE_ID` (optional): Specific Notion page ID to monitor (if not set, all accessible pages will be monitored)
- `POLLING_INTERVAL`: Time in seconds between polling cycles (default: 60)
- `PORT`: Port for the Flask web server (default: 5001)

## Usage

Start the application:

```
python app.py
```

The service will:
1. Start polling Notion for new comments at the specified interval
2. Process any new comments by echoing them back as replies
3. Expose API endpoints for monitoring and control

## API Endpoints

- `/health`: Health check endpoint
- `/status`: Service status and statistics
- `/manual-poll`: Trigger an immediate polling cycle

## Future Enhancements

This application is designed to be extended with more advanced features, such as:

- LLM integration for intelligent responses
- Custom response templates
- User feedback mechanisms
- Advanced analytics

## Note

This is a demonstration application that currently only echoes comments. The codebase includes references to a more advanced implementation that would use a Large Language Model (LLM) for generating intelligent responses, as outlined in the included PRD document.
