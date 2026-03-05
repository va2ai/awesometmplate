# Awesome Knowledge Base

AI-powered knowledge base that turns topics, URLs, and files into rich, structured pages -- powered by Claude.

Drop in a topic like "React vs Vue" or paste a documentation URL, and Claude researches it, organizes it into sections with mixed block types (code grids, comparisons, stats, FAQs, timelines, badges), and routes it to the right page automatically.

## Features

**AI-Powered Content Generation**
- Research any topic -- Claude generates structured sections with real web sources (via Exa)
- Smart Add -- Claude decides where new content fits in existing pages
- Ask AI -- free-form chat to describe exactly what you want added
- Auto-routing -- Haiku classifies topics and routes to the right page

**14 Block Types**
- `code_grid` `info_grid` `comparison` `stats` `steps` `table`
- `faq` `timeline` `badges` `checklist` `tip` `alert` `text` `link_list`
- Custom block type designer -- AI creates new block types with Jinja2 templates

**Production Ready**
- Async job system with toast notifications and polling
- Job recovery on server restart (stuck jobs marked failed)
- Structured logging, CORS, SSRF prevention, no tracebacks in responses
- Docker deployment, env-based config
- iOS-optimized mobile view with PWA support

## Architecture

```
                    +------------------+
                    |   FastAPI App    |
                    |   (main.py)      |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
        +-----+----+  +-----+----+  +------+-----+
        |  Routes   |  |  Agents  |  |  Services   |
        +----------+  +----------+  +------------+
        | home.py  |  | researcher|  | exa_search |
        | pages.py |  | router    |  | url_fetcher|
        | api.py   |  | merger    |  | job_manager|
        | jobs.py  |  | smart_add |  | claude.py  |
        +----------+  | taxonomist|  +------------+
                       | block_dgn |
                       +-----+-----+
                             |
                       +-----+-----+
                       |   Tools   |
                       +-----------+
                       | api.py    |  <-- Single Claude API caller
                       | schemas.py|  <-- Tool-use schemas
                       | tracker.py|  <-- Token cost tracking
                       +-----------+
```

**Design Principle: Tools vs Agents vs Services**
- **Tools** -- Pure schemas + API caller. No business logic.
- **Agents** -- Compose tools to accomplish tasks. Each has a role.
- **Services** -- Data I/O (file read/write, web fetching, job persistence).
- **Routes** -- Import from agents, never from tools directly.

**AI Pipeline**
```
User Input -> Haiku (route) -> Sonnet (research/merge) -> Haiku (taxonomy check)
                                     |
                              Exa Web Search (async, 30s timeout)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.12, async/await |
| AI | Claude API (Sonnet 4 + Haiku 4.5) via httpx tool_use |
| Search | Exa SDK (AsyncExa) for web research grounding |
| Frontend | Jinja2 templates, Tailwind CSS, Iconify (Phosphor) |
| Data | JSON files on disk (pages, jobs, tokens, custom blocks) |
| Deploy | Docker + Gunicorn + Uvicorn workers |

## Quick Start

```bash
# Clone
git clone https://github.com/va2ai/awesometmplate.git
cd awesometmplate

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY (required) and EXA_API_KEY (optional)

# Run
python main.py
# Open http://localhost:3339
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | -- | Claude API key |
| `EXA_API_KEY` | No | -- | Exa web search for research grounding |
| `ENV` | No | `dev` | `dev` or `prod` |
| `PORT` | No | `3339` | Server port |
| `LOG_LEVEL` | No | `DEBUG` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `API_TIMEOUT` | No | `300` | Claude API timeout in seconds |

## Docker

```bash
docker build -t awesome-kb .
docker run -p 8080:8080 --env-file .env -e ENV=prod awesome-kb
```

## Project Structure

```
awesometmplate/
  app/
    __init__.py        # App factory, CORS, lifespan, autoescape
    config.py          # Env vars, logging, paths, pricing
    models/            # Pydantic models (blocks, directory, site)
    routes/            # FastAPI endpoints (home, pages, api, jobs)
    agents/            # AI orchestration (researcher, router, merger, etc.)
    services/          # Data I/O (exa_search, job_manager, url_fetcher)
    tools/             # Claude API caller, schemas, token tracker
  templates/           # Jinja2 HTML (home.html, page.html)
  static/              # CSS, JS assets
  data/                # Runtime data (pages JSON, jobs, token usage)
  main.py              # Entry point
  Dockerfile           # Production container
  requirements.txt     # Pinned dependencies
```

## How It Works

1. **Add a topic** from the home page -- type "Kubernetes" or paste a URL
2. **Haiku routes it** to the best page (Programming, VA, Misc, etc.)
3. **Exa searches the web** for real sources (async, 30s timeout)
4. **Sonnet generates** structured sections with mixed block types
5. **Content merges** with existing page data (never overwrites)
6. **Job toast** shows progress -- poll until complete, then view the page

## Key Technical Decisions

- **httpx instead of Anthropic SDK** -- direct API calls with tool_use for structured output, no SDK overhead
- **Haiku for routing, Sonnet for content** -- cost optimization ($0.80/M vs $3/M input)
- **AsyncExa with timeout** -- Exa SDK is sync-native, wrapped in AsyncExa with 30s timeout to prevent hangs
- **JSON file storage** -- simple, no database dependency, thread-safe with locks
- **Job recovery on restart** -- marks stuck "running" jobs as failed so frontend handles gracefully
- **Merge-not-replace** -- research and Ask AI merge new sections with existing content

## License

MIT
