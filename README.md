# Notion Comments Polling Service

This application monitors Notion pages for new comments and stores them in a database. The service polls the Notion API at regular intervals to check for new comments and tracks their status.

## Architecture

The system is a simple polling service:

- **Polling Service**: Polls Notion API at regular intervals to check for new comments
- **SQLite Database**: Stores comment data and status

## Setup

### Prerequisites

- Docker and Docker Compose
- Notion API Key

### Configuration

1. Copy the sample environment file and fill in your API keys:

```bash
cp .env.sample .env
```

2. Edit the `.env` file with your API keys and settings:

```
NOTION_API_KEY=your_notion_api_key_here
NOTION_PAGE=your_notion_page_id_here
```

## Running the Application

### Using Docker Compose

Build and start the service:

```bash
docker-compose up -d
```

### Running Without Docker

```bash
python app.py
```

## API Endpoints

- `/health` - Health check endpoint
- `/status` - Service status and statistics
- `/manual-poll` - Trigger an immediate polling cycle

## Development

To run the service locally without Docker:

```bash
python app.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| NOTION_API_KEY | Your Notion API key | (required) |
| NOTION_PAGE | ID of the Notion page to monitor | (required) |
| POLLING_INTERVAL | Interval in seconds between polling cycles | 60 |
| PORT | Port for the polling service | 5001 |
