# Guzu MCP Server

Remote MCP server for Guzu AI Visibility.

## Deploy on Railway

1. Create a new Railway service
2. Point it to this file / repo
3. Set environment variable:
   - `GUZU_BASE_URL` = `https://web-production-9c5d.up.railway.app`
4. Railway will assign a URL like `https://guzu-mcp.up.railway.app`

## Connect to Claude

```bash
claude mcp add --transport http guzu https://guzu-mcp.up.railway.app/sse
```

## Tools

| Tool | Credits | What it does |
|------|---------|-------------|
| `get_visibility_score` | 1 | AI Visibility Index + platform breakdown |
| `get_citation_trends` | 1 | Day-by-day citation trends |
| `get_query_results` | 1 | Per-query results across platforms |
| `compare_competitors` | 3 | Competitor rankings + radar metrics |
| `ask_guzu` | 10 | Natural language AI visibility analysis |

## Usage in Claude

```
get_visibility_score(api_key="gzu_xxx", brand_id=1)
ask_guzu(api_key="gzu_xxx", brand_id=1, question="Why is my visibility dropping?")
```
