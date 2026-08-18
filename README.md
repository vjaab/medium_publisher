# Medium Auto Publisher

An automated daily publishing pipeline that generates high-quality, original technical articles and publishes them to Medium.

## Overview

This system automatically:
1. **Selects topics** from configurable categories using AI scoring
2. **Researches topics** using web search APIs and official sources
3. **Writes articles** with practical code examples and technical depth
4. **Reviews content** for accuracy, clarity, and quality
5. **Optimizes SEO** with titles, tags, and metadata
6. **Formats for Medium** with proper Markdown structure
7. **Publishes** via Medium API (creates drafts)
8. **Tracks history** in SQLite to prevent duplicates

## Architecture

```
medium-auto-publisher/
├── src/
│   ├── main.py                 # Pipeline orchestration & CLI
│   ├── config.py               # Configuration management
│   ├── research/
│   │   ├── topic_finder.py     # Topic generation & scoring
│   │   └── web_researcher.py   # Web search & research extraction
│   ├── content/
│   │   ├── writer.py           # Article generation
│   │   ├── editor.py           # Fact-check & quality review
│   │   ├── seo.py              # SEO optimization
│   │   └── formatter.py        # Medium Markdown formatting
│   ├── publishing/
│   │   ├── publisher.py        # Abstract publisher interface
│   │   └── medium.py           # Medium API implementation
│   ├── storage/
│   │   └── database.py         # SQLite article storage
│   └── utils/
│       ├── logger.py           # Structured logging
│       └── helpers.py          # Retry logic, text utilities
├── prompts/                    # LLM prompts for each stage
├── tests/                      # Unit tests
├── data/                       # SQLite database
├── logs/                       # Execution logs
├── output/                     # Dry-run article output
└── .github/workflows/          # GitHub Actions CI/CD
```

## Quick Start

### Prerequisites

- Python 3.12+
- API keys for:
  - LLM provider (OpenAI or Anthropic)
  - Search provider (SerpAPI, Tavily, or DuckDuckGo)
  - Medium integration token

### Installation

```bash
# Clone repository
git clone <repo-url>
cd medium-auto-publisher

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` with your credentials:

```env
LLM_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o

SEARCH_API_KEY=...
SEARCH_PROVIDER=serpapi

MEDIUM_TOKEN=...
MEDIUM_PUBLICATION_ID=optional

DRY_RUN=false
```

### Running Locally

```bash
# Dry run (generates article but doesn't publish)
python -m src.main --dry-run

# Publish manually
python -m src.main --publish

# Publish specific topic
python -m src.main --topic "Spring Boot Virtual Threads" --publish

# Validate config
python -m src.main --config-check
```

## GitHub Actions Deployment

The pipeline runs automatically daily at 03:30 UTC (09:00 IST) via GitHub Actions.

### Required Secrets

Add these in GitHub Repository Settings → Secrets → Actions:

| Secret | Description |
|--------|-------------|
| `LLM_API_KEY` | OpenAI or Anthropic API key |
| `LLM_PROVIDER` | `openai` or `anthropic` |
| `LLM_MODEL` | Model name (e.g., `gpt-4o`, `claude-3-opus`) |
| `SEARCH_API_KEY` | SerpAPI or Tavily API key |
| `SEARCH_PROVIDER` | `serpapi`, `tavily`, or `duckduckgo` |
| `MEDIUM_TOKEN` | Medium integration token |
| `MEDIUM_PUBLICATION_ID` | Optional: Publication ID for posting to publication |

### Optional Secrets

| Secret | Default | Description |
|--------|---------|-------------|
| `ARTICLES_PER_DAY` | `1` | Articles to publish daily |
| `MIN_ARTICLE_WORDS` | `1200` | Minimum article length |
| `MAX_ARTICLE_WORDS` | `2000` | Maximum article length |
| `CONTENT_CATEGORIES` | See `.env.example` | Comma-separated categories |
| `ENABLE_RESEARCH` | `true` | Enable web research |
| `ENABLE_FACT_CHECK` | `true` | Enable editorial review |
| `ENABLE_DUPLICATE_CHECK` | `true` | Enable duplicate detection |
| `DRY_RUN` | `false` | Run without publishing |

### Manual Trigger

Go to Actions → Daily Medium Publisher → Run workflow. Options:
- `dry_run`: Generate article without publishing
- `topic`: Specify a manual topic

## Medium Publishing Limitations

**Important:** Medium's official API has limitations:

1. **Only creates drafts** - Cannot publish directly to "public" status
2. **No image upload** - Images must be added manually
3. **No canonical URL** - Cannot set `canonicalUrl` via API
4. **Publication posting** - Requires publication ID and permissions

### Workflow

1. Pipeline creates article as **draft** on Medium
2. **Manual step required**: Go to Medium.com → Drafts → Click "Publish"
3. For publications: Select publication in Medium editor before publishing

### Alternatives (Not Implemented)

- Selenium/Playwright automation for full publishing
- Medium's RSS import feature
- Third-party publishing services

## Content Quality Rules

The system enforces:
- No copied/rewritten content from other sites
- No invented sources, statistics, or personal experiences
- No duplicate topics without substantial new value
- Quality over schedule - skips day if research insufficient
- Technical accuracy verified by separate review pass

## Customization

### Adding Categories

Edit `CONTENT_CATEGORIES` in `.env` or GitHub secrets.

### Modifying Prompts

Edit files in `prompts/`:
- `topic_selection.txt` - Topic generation
- `research.txt` - Research extraction
- `article_writer.txt` - Article writing
- `editor.txt` - Quality review
- `seo.txt` - SEO metadata

### Changing LLM Provider

Set `LLM_PROVIDER=anthropic` and `LLM_MODEL=claude-3-opus-20240229`.

### Changing Search Provider

Set `SEARCH_PROVIDER=tavily` or `duckduckgo` (free, no API key needed).

## Database

SQLite database at `data/articles.db` tracks:

```sql
articles (
  id, topic, title, subtitle, content, tags, sources,
  published_at, medium_url, status, content_hash,
  error_message, created_at, updated_at
)
```

Statuses: `TOPIC_SELECTED` → `RESEARCHED` → `GENERATED` → `REVIEWED` → `READY` → `PUBLISHED`/`FAILED`

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Troubleshooting

### Pipeline fails silently

Check `logs/pipeline.log` for detailed error messages.

### "Today's article already published"

The idempotency check prevents duplicate daily runs. To force re-run:
- Delete today's entry from database
- Or use `--topic` with manual topic

### Medium publishing fails

1. Verify `MEDIUM_TOKEN` is valid integration token
2. Check token has "Publish to publications" scope
3. For publications: verify `MEDIUM_PUBLICATION_ID` is correct

### Low quality articles

1. Check research sources in logs
2. Adjust prompts in `prompts/`
3. Increase `MIN_ARTICLE_WORDS`
4. Enable `ENABLE_FACT_CHECK=true`

### Rate limits

- Increase `RETRY_ATTEMPTS` and `RETRY_BASE_DELAY`
- Add delays between API calls in code

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork repository
2. Create feature branch
3. Add tests for new functionality
4. Run `pytest` and `ruff check src/`
5. Submit PR

## Known Limitations

- Medium API only creates drafts (manual publish required)
- No image generation/upload
- Search quality depends on provider
- LLM costs vary by provider/model
- No multi-language support
- Single article per day by design