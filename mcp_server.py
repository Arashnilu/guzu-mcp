import os
import httpx
from mcp.server.fastmcp import FastMCP

GUZU_BASE_URL = os.getenv("GUZU_BASE_URL", "https://web-production-9c5d.up.railway.app")

mcp = FastMCP("Guzu AI Visibility")
app = mcp.sse_app()


def _auth(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


def _get_cross_source(api_key: str, brand_id: int, days: int = 7) -> dict:
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


@mcp.tool()
def get_visibility_score(api_key: str, brand_id: int, days: int = 7) -> dict:
    """Get the AI Visibility Index and summary stats for a brand."""
    data = _get_cross_source(api_key, brand_id, days)
    stats = data.get("summary_stats", {})
    return {
        "brand_id":            brand_id,
        "days":                days,
        "ai_visibility_index": data.get("ai_visibility_index", 0),
        "total_citations":     data.get("total_citations", 0),
        "total_mentions":      data.get("total_mentions", 0),
        "total_visibility":    data.get("total_visibility", 0),
        "market_position":     stats.get("market_position"),
        "platforms":           data.get("platform_comparison", [])
    }


@mcp.tool()
def get_citation_trends(api_key: str, brand_id: int, days: int = 7) -> dict:
    """Get day-by-day citation and mention trends for a brand."""
    data = _get_cross_source(api_key, brand_id, days)
    return {
        "brand_id":   brand_id,
        "days":       days,
        "trend_data": data.get("trend_data", []),
    }


@mcp.tool()
def get_query_results(api_key: str, brand_id: int, days: int = 7) -> dict:
    """Get per-query brand mention results across AI platforms."""
    data = _get_cross_source(api_key, brand_id, days)
    return {
        "brand_id":               brand_id,
        "days":                   days,
        "cross_platform_queries": data.get("cross_platform_queries", []),
        "category_performance":   data.get("category_performance", []),
    }


@mcp.tool()
def compare_competitors(api_key: str, brand_id: int, days: int = 7) -> dict:
    """Compare the brand's AI visibility against its competitors."""
    data = _get_cross_source(api_key, brand_id, days)
    return {
        "brand_id":             brand_id,
        "days":                 days,
        "competitor_data":      data.get("competitor_data", {}),
        "radar_metrics":        data.get("radar_metrics", {}),
        "platform_competitors": data.get("platform_specific_competitors", {}),
    }


@mcp.tool()
def ask_guzu(api_key: str, brand_id: int, question: str, days: int = 7) -> dict:
    """Ask a natural language question about a brand's AI visibility."""
    data = _get_cross_source(api_key, brand_id, days)
    stats   = data.get("summary_stats", {})
    comp    = data.get("competitor_data", {})
    trends  = data.get("trend_data", [])
    queries = data.get("cross_platform_queries", [])
    return {
        "brand_id": brand_id,
        "question": question,
        "data": {
            "ai_visibility_index": data.get("ai_visibility_index"),
            "total_citations":     data.get("total_citations"),
            "total_mentions":      data.get("total_mentions"),
            "market_position":     stats.get("market_position"),
            "platforms":           data.get("platform_comparison", []),
            "trend_data":          trends[-7:] if trends else [],
            "top_queries":         queries[:10] if queries else [],
            "competitor_ranking":  comp.get("overall_ranking", [])[:5],
        },
        "note": "Use the data above to answer the question with specific numbers and actionable insights."
    }

if __name__ == "__main__":
    os.environ["UVICORN_HOST"] = "0.0.0.0"
    os.environ["UVICORN_PORT"] = os.environ.get("PORT", "8080")
    mcp.run(transport="sse")
