# Guzu MCP — AI Brand Visibility for Claude, Cursor & Windsurf

Connect your AI assistant to [Guzu](https://guzu.ai) and see how your brand shows up across AI platforms — ChatGPT, Perplexity, Gemini, and Google AI Overviews. Find where you're cited, where competitors beat you, and exactly which gaps to close.

> **Free to start.** Create a developer account, get free credits, no credit card required.

---

## What it does

People increasingly ask AI assistants instead of searching Google. If those assistants don't cite or mention your brand, you're invisible to that traffic. Guzu measures your **AI visibility** — citations + mentions — across the major AI platforms, and shows you the specific opportunities to improve it.

This MCP server brings that data straight into your AI coding assistant. Point it at a website, and your assistant can analyze the brand, track it across platforms, and pull back visibility scores, competitor comparisons, and citation-gap analysis — all in conversation.

---

## Quick start

### 1. Get an API key
Create a free developer account at **[guzu.ai/mcp](https://guzu.ai/mcp)** and copy your API key (starts with `gzu_`).

### 2. Connect your client

**Claude Code**
```bash
claude mcp add --transport sse guzu \
  https://guzu-mcp-production.up.railway.app/sse \
  --header "X-Guzu-Api-Key: gzu_YOUR_KEY"
```

**Cursor / Windsurf** — add to your MCP config:
```json
{
  "mcpServers": {
    "guzu": {
      "url": "https://guzu-mcp-production.up.railway.app/sse",
      "headers": {
        "X-Guzu-Api-Key": "gzu_YOUR_KEY"
      }
    }
  }
}
```

### 3. Restart your client
Your assistant will now have the Guzu tools available. Try: *"Analyze ringgitplus.com for AI visibility."*

---

## Tools

| Tool | What it does |
|------|--------------|
| `prepare_brand` | Scan a website and build a draft tracking profile (offers, competitors, prompts) to review before committing |
| `start_analyzing` | Save the prepared brand and start collecting AI-visibility data across platforms; returns a `brand_id` |
| `check_analyzing_progress` | See which AI platforms have finished collecting data |
| `get_visibility_score` | AI Visibility Index, total citations & mentions, market position, per-platform breakdown |
| `compare_competitors` | How the brand ranks against competitors, overall and per platform |
| `get_results_by_prompt` | Which tracked prompts the brand shows up on, plus performance by category |
| `gap_analysis` | Where the brand is missing from AI answers — opportunity domains, content-type mix, and citation gaps (per platform or all at once) |
| `ask_guzu` | Ask a natural-language question about a brand's AI visibility |

### Typical workflow
1. **`prepare_brand`** → review the profile, offers, competitors, and prompts (edit if you like)
2. **`start_analyzing`** → kicks off the analysis across AI platforms (~10–12 min)
3. **`check_analyzing_progress`** → poll until platforms are done
4. **`get_visibility_score`**, **`compare_competitors`**, **`gap_analysis`** → read your results

---

## Supported clients

Header-based connection works with:

- Claude Code
- Cursor
- Windsurf

> Claude.ai web, Claude Desktop, and Cowork use a cloud-brokered connector flow that requires OAuth — support for those is on the roadmap.

---

## Platform coverage notes

- Visibility is tracked across **ChatGPT, Perplexity, Gemini, and Google AI Overviews**.
- Full **gap & mention** detail (who's cited, who's mentioned, you-vs-rival gaps) is available for **ChatGPT** and **AI Overviews**. Other platforms report accurate **citation frequency** but not the full gap breakdown.

---

## Credits

- A free developer account starts with bonus credits.
- Preparing and analyzing a brand consumes credits; reading results is free.
- See live pricing and top up at **[guzu.ai/mcp](https://guzu.ai/mcp)**.

---

## Links

- **Website:** [guzu.ai](https://guzu.ai)
- **Get started / dashboard:** [guzu.ai/mcp](https://guzu.ai/mcp)
