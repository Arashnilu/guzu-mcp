"""
mcp_server.py — Guzu AI Visibility MCP Server
Deploy as a separate Railway service.

Tools exposed:
  - get_visibility_score
  - get_citation_trends
  - get_query_results
  - compare_competitors
  - ask_guzu

Each tool requires an api_key (gzu_xxx) generated from the Guzu dashboard.
"""

import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

GUZU_BASE_URL = os.getenv("GUZU_BASE_URL", "https://web-production-9c5d.up.railway.app")

mcp = FastMCP("Guzu AI Visibility")


def _auth(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


def _get_cross_source(api_key: str, brand_id: int, days: int = 7) -> dict:
    """Shared helper — fetches cross-source-data and returns the full payload."""
    r = httpx.get(
        f"{GUZU_BASE_URL}/api/overview/cross-source-data",
        params={"brand_id": brand_id, "days": days},
        headers=_auth(api_key),
        timeout=30
    )
    if r.status_code == 401:
        raise ValueError("Invalid or expired API key")
    if r.status_code == 403:
        raise ValueError("Brand not found or does not belong to this account")
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — get_visibility_score  (1 credit)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_visibility_score(api_key: str, brand_id: int, days: int = 7) -> dict:
    """
    Get the AI Visibility Index and summary stats for a brand.

    Returns the overall AI Visibility Index (0-100), total citations,
    total mentions, and per-platform breakdown for the given period.

    Args:
        api_key:  Your Guzu API key (gzu_...)
        brand_id: The brand ID from your Guzu account
        days:     Lookback window in days (default 7)
    """
    data = _get_cross_source(api_key, brand_id, days)
    stats = data.get("summary_stats", {})
    platforms = data.get("platform_comparison", [])

    return {
        "brand_id":           brand_id,
        "days":               days,
        "ai_visibility_index": data.get("ai_visibility_index", 0),
        "total_citations":    data.get("total_citations", 0),
        "total_mentions":     data.get("total_mentions", 0),
        "total_visibility":   data.get("total_visibility", 0),
        "avg_citation_ratio": stats.get("avg_ratio", 0),
        "market_position":    stats.get("market_position"),
        "platforms":          [
            {
                "source":    p.get("source"),
                "citations": p.get("citations", 0),
                "mentions":  p.get("mentions", 0),
            }
            for p in platforms
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — get_citation_trends  (1 credit)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_citation_trends(api_key: str, brand_id: int, days: int = 7) -> dict:
    """
    Get day-by-day citation and mention trends for a brand.

    Returns a time-series of citations and mentions per AI platform
    so you can see how visibility is changing over time.

    Args:
        api_key:  Your Guzu API key (gzu_...)
        brand_id: The brand ID from your Guzu account
        days:     Lookback window in days (default 7)
    """
    data = _get_cross_source(api_key, brand_id, days)
    return {
        "brand_id":   brand_id,
        "days":       days,
        "trend_data": data.get("trend_data", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — get_query_results  (1 credit)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_query_results(api_key: str, brand_id: int, days: int = 7) -> dict:
    """
    Get per-query brand mention results across AI platforms.

    Shows which tracked queries mention the brand, across ChatGPT,
    Claude, Gemini, Perplexity and other enabled AI sources.

    Args:
        api_key:  Your Guzu API key (gzu_...)
        brand_id: The brand ID from your Guzu account
        days:     Lookback window in days (default 7)
    """
    data = _get_cross_source(api_key, brand_id, days)
    return {
        "brand_id":              brand_id,
        "days":                  days,
        "cross_platform_queries": data.get("cross_platform_queries", []),
        "category_performance":  data.get("category_performance", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 — compare_competitors  (3 credits)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def compare_competitors(api_key: str, brand_id: int, days: int = 7) -> dict:
    """
    Compare the brand's AI visibility against its competitors.

    Returns competitor rankings, market position, and radar metrics
    showing how the brand stacks up across citation and mention dimensions.

    Args:
        api_key:  Your Guzu API key (gzu_...)
        brand_id: The brand ID from your Guzu account
        days:     Lookback window in days (default 7)
    """
    data = _get_cross_source(api_key, brand_id, days)
    return {
        "brand_id":             brand_id,
        "days":                 days,
        "competitor_data":      data.get("competitor_data", {}),
        "radar_metrics":        data.get("radar_metrics", {}),
        "platform_competitors": data.get("platform_specific_competitors", {}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5 — ask_guzu  (10 credits)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def ask_guzu(api_key: str, brand_id: int, question: str, days: int = 7) -> dict:
    """
    Ask a natural language question about a brand's AI visibility.

    Fetches full visibility data and returns a structured answer
    to questions like: "Why is my visibility dropping?" or
    "Which AI platform should I focus on?" or
    "How do I compare to my top competitor?"

    Args:
        api_key:  Your Guzu API key (gzu_...)
        brand_id: The brand ID from your Guzu account
        question: Your question in plain English
        days:     Lookback window in days (default 7)
    """
    data = _get_cross_source(api_key, brand_id, days)

    # Build a compact context summary for the AI to reason over
    stats   = data.get("summary_stats", {})
    comp    = data.get("competitor_data", {})
    trends  = data.get("trend_data", [])
    queries = data.get("cross_platform_queries", [])

    context = {
        "question":            question,
        "brand_id":            brand_id,
        "days":                days,
        "ai_visibility_index": data.get("ai_visibility_index"),
        "total_citations":     data.get("total_citations"),
        "total_mentions":      data.get("total_mentions"),
        "market_position":     stats.get("market_position"),
        "avg_ratio":           stats.get("avg_ratio"),
        "platforms":           data.get("platform_comparison", []),
        "trend_data":          trends[-7:] if trends else [],
        "top_queries":         queries[:10] if queries else [],
        "competitor_ranking":  comp.get("overall_ranking", [])[:5],
        "category_performance": data.get("category_performance", []),
    }

    return {
        "brand_id": brand_id,
        "question": question,
        "data":     context,
        "note":     "Use the data above to answer the question with specific numbers and actionable insights."
    }


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", 8001))
    mcp.run(transport="sse")
