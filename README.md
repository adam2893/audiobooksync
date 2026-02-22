# AudioBook Sync

Synchronize your audiobook progress from AudiobookShelf to Hardcovers and StoryGraph automatically.

## Features

- 📚 **Cross-Platform Sync**: Automatically sync audiobook progress from AudiobookShelf to Hardcovers and StoryGraph
- 🔄 **Periodic Polling**: Configurable sync intervals (default: 10 minutes)
- 🔍 **Smart Book Matching**: ISBN-based matching with fuzzy title/author fallback
- 🎯 **Manual Overrides**: Override auto-matched books and manually select correct matches
- 💾 **Persistent Storage**: SQLite database for mappings and sync history (no external services needed!)
- 🌐 **Web UI**: Beautiful setup wizard and dashboard for easy configuration
- 📋 **Error Handling**: Clear error messages with actionable suggestions for users
- 🚀 **Lightweight**: Optimized for minimal resource usage on systems like Unraid

## Prerequisites

- Docker and Docker Compose
- AudiobookShelf instance with API access
- Hardcovers account (optional, but recommended)
- StoryGraph account (optional, but recommended)

## Quick Start

### Option A: Using Pre-built Image (Recommended)

```bash
# Create .env file
cat > .env << EOF
AUDIOBOOKSHELF_URL=http://your-abs-instance:13378
AUDIOBOOKSHELF_API_KEY=your_abs_api_key
HARDCOVERS_API_KEY=your_hardcovers_key
STORYGRAPH_SESSION_COOKIE=your_storygraph_cookie
EOF

# Run with pre-built image from GitHub Container Registry
docker run -d \
  --name audiobook-sync \
  -p 8000:8000 \
  -v audiobook-sync-data:/data \
  --env-file .env \
  ghcr.io/adam2893/audiobooksync:latest
```

### Option B: Clone and Build Locally

```bash
git clone https://github.com/adam2893/audiobooksync.git
cd audiobooksync
cp .env.example .env
```

Edit `.env` with your values:

```env
AUDIOBOOKSHELF_URL=http://your-abs-instance:13378
AUDIOBOOKSHELF_API_KEY=your_abs_api_key
HARDCOVERS_API_KEY=your_hardcovers_key
STORYGRAPH_SESSION_COOKIE=your_storygraph_cookie
```

Run with Docker Compose:

```bash
docker-compose up -d
```

The web UI will be available at `http://localhost:8000`

## Configuration

### AudiobookShelf API Key

1. Go to AudiobookShelf admin panel
2. Settings → API Tokens
3. Create a new token and copy it

### Hardcovers API Key

1. Go to https://hardcover.app/account/api
2. Generate or copy your API key

### StoryGraph Session Cookie

1. Go to https://storygraph.com and log in
2. Press F12 to open Developer Tools
3. Go to Application → Cookies → storygraph.com
4. Find `_storygraph_session` and copy its value
5. Paste into the setup wizard

## Architecture

```
┌─────────────────────────────────────────────────────┐
│        AudioBook Sync Container (Docker)            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  FastAPI Web UI (Setup Wizard + Dashboard)         │
│  ├─ Configuration Validation                       │
│  ├─ Connection Testing                             │
│  └─ Book Matching Interface                        │
│                                                     │
│  APScheduler (Periodic Sync)                       │
│  ├─ Poll AudiobookShelf every N minutes            │
│  ├─ Fetch current audiobook progress               │
│  └─ Queue sync tasks                               │
│                                                     │
│  Sync Engine                                        │
│  ├─ Book Matching (ISBN → Fuzzy Matching)          │
│  ├─ Progress Transformation                        │
│  └─ Platform Sync Workers                          │
│                                                     │
│  SQLite Database                                    │
│  ├─ Book mappings (AudiobookShelf ↔ Platforms)    │
│  ├─ Sync history and logs                          │
│  └─ Application state                              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Project Structure

```
audiobook-sync/
├── src/
│   ├── apis/                    # API client modules
│   │   ├── audiobookshelf.py   # AudiobookShelf REST client
│   │   ├── hardcovers.py       # Hardcovers GraphQL client
│   │   └── storygraph.py       # StoryGraph wrapper client
│   ├── sync/                    # Sync orchestration
│   │   ├── matcher.py          # Book matching engine
│   │   ├── worker.py           # Progress sync worker
│   │   └── scheduler.py        # APScheduler integration
│   ├── ui/                      # Web UI
│   │   ├── app.py              # FastAPI application
│   │   └── index.html          # Setup wizard & dashboard
│   ├── config.py               # Configuration management
│   ├── logger.py               # Logging setup
│   ├── models.py               # SQLAlchemy models
│   └── main.py                 # Application entry point
├── docker/
│   └── Dockerfile              # Container image
├── docker-compose.yml          # Docker Compose configuration
├── requirements.txt            # Python dependencies
├── .env.example                # Example environment variables
└── README.md                   # This file
```

## How It Works

### 1. Setup Wizard (First Run)

- User provides AudiobookShelf, Hardcovers, and StoryGraph credentials
- Application validates each connection
- User chooses to auto-match existing books or match manually later

### 2. Book Matching

- **Primary Method**: ISBN matching across platforms
- **Fallback Method**: Fuzzy title/author matching with confidence scoring
- **Manual Override**: Users can correct any auto-matched or missed books
- Matches stored in SQLite database

### 3. Periodic Sync

- APScheduler polls AudiobookShelf every N minutes (configurable)
- Retrieves current listening progress for each book
- For each mapped book:
  - Calculates progress percentage
  - Syncs to Hardcovers (via GraphQL)
  - Syncs to StoryGraph (via wrapper library)
- Respects API rate limits (Hardcovers: 60 req/min)

### 4. One-Way Sync

- AudiobookShelf is the source of truth
- Progress flows: AudiobookShelf → Hardcovers/StoryGraph
- Unmapped books are skipped without errors

## API Endpoints

### Health & Status

- `GET /api/health` - Health check
- `GET /api/status` - Application status and statistics
- `GET /api/config/display` - Read-only configuration

### Configuration

- `GET /api/config/errors` - Configuration validation errors
- `POST /api/config/validate` - Validate current configuration

### Validation

- `POST /api/validate/audiobookshelf` - Test AudiobookShelf connection
- `POST /api/validate/hardcovers` - Test Hardcovers connection
- `POST /api/validate/storygraph` - Test StoryGraph connection

## Troubleshooting

### Configuration Errors

The web UI displays clear error messages with suggestions:

- **Missing AudiobookShelf URL**: "Set AUDIOBOOKSHELF_URL environment variable (e.g., http://localhost:13378)"
- **Invalid Hardcovers API key**: "Get it from hardcover.app/account/api"
- **Expired StoryGraph cookie**: "Extract a fresh cookie from your browser"

### Books Not Matching

1. Check the book's ISBN in AudiobookShelf
2. Use the manual book mapping interface to search and select the correct match
3. Verify titles and authors match across platforms

### Sync Not Running

1. Check application logs: `docker-compose logs audiobook-sync`
2. Verify all credentials are correct
3. Test each platform connection in the web UI

### StoryGraph Session Expired

- Re-extract the session cookie and update in web UI or `.env` file
- Restart container: `docker-compose restart audiobook-sync`

## Logs

View application logs:

```bash
docker-compose logs -f audiobook-sync
```

Set log level in `.env`:

```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

## Development

### Local Setup

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run Locally

```bash
export $(cat .env | xargs)
python -m src.main
```

### Run Tests

```bash
pytest tests/
```

## Docker Image

Pre-built images are automatically published to GitHub Container Registry whenever code is pushed to the main branch.

**Image**: `ghcr.io/adam2893/audiobooksync:latest`

Pull the latest image:

```bash
docker pull ghcr.io/adam2893/audiobooksync:latest
```

## Unraid Deployment

Create an Unraid container template using the pre-built image or docker-compose.yml. Users can:

1. Map `/data` volume to persist SQLite database
2. Set environment variables for each credential
3. Map port `8000` to access web UI

## Limitations

- **One-Way Sync**: Currently syncs from AudiobookShelf only
- **StoryGraph Cookie**: Requires manual extraction (Cloudflare protection)
- **Rate Limiting**: Respects Hardcovers 60 req/min limit
- **Book Matching**: Best-effort; manual overrides available

## Future Enhancements

- [ ] Bi-directional sync support
- [ ] Advanced book search UI with cover images
- [ ] Sync notifications/alerts
- [ ] Support for more platforms
- [ ] Web scraping for additional metadata
- [ ] Automated sync job retry logic
- [ ] Export sync logs

## License

[Add license info]

## Support

For issues, feature requests, or contributions, please open a GitHub issue.
