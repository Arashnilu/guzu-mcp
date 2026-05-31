import os
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from contextvars import ContextVar

GUZU_BASE_URL = os.getenv("GUZU_BASE_URL", "https://web-production-9c5d.up.railway.app")

# Context var to hold the API key for the current request
_api_key_var: ContextVar[str] = ContextVar("api_key", default="")

mcp = FastMCP(
    "Guzu AI Visibility",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)

app = mcp.sse_app()

# ── Middleware to extract API key from headers ────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract key from Authorization: Bearer gzu_... or X-Guzu-Api-Key header
        api_key = ""
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer gzu_"):
            api_key = auth[7:]
        elif request.headers.get("x-guzu-api-key", "").startswith("gzu_"):
            api_key = request.headers.get("x-guzu-api-key")

        # For SSE endpoint, key is required
        if request.url.path == "/sse" and not api_key:
            return JSONResponse(
                {"error": "API key required. Pass X-Guzu-Api-Key header."},
                status_code=401
            )

        token = _api_key_var.set(api_key)
        try:
            response = await call_next(request)
        finally:
            _api_key_var.reset(token)
        return response

app.add_middleware(ApiKeyMiddleware)


# ── Shared helper ─────────────────────────────────────────────────────────────
def _get_cross_source(brand_id: int, days: int = 7) -> dict:
    api_key = _api_key_var.get()
    if not api_key:
        raise ValueError("No API key found. Connect with X-Guzu-Api-Key header.")

    r = httpx.get(
        f"{GUZU_BASE_URL}/api/overview/cross-source-data",
        params={"brand_id": brand_id, "days": days},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30
    )
    if r.status_code == 401:
        raise ValueError("Invalid or expired API key")
    if r.status_code == 403:
        raise ValueError("Brand not found or does not belong to this account")
    r.raise_for_status()
    return r.json()


# ── Tools (no api_key param needed) ──────────────────────────────────────────

@mcp.tool()
def get_visibility_score(brand_id: int, days: int = 7) -> dict:
    """Get the AI Visibility Index and summary stats for a brand."""
    data = _get_cross_source(brand_id, days)
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
def get_citation_trends(brand_id: int, days: int = 7) -> dict:
    """Get day-by-day citation and mention trends for a brand."""
    data = _get_cross_source(brand_id, days)
    return {
        "brand_id":   brand_id,
        "days":       days,
        "trend_data": data.get("trend_data", []),
    }


@mcp.tool()
def get_query_results(brand_id: int, days: int = 7) -> dict:
    """Get per-query brand mention results across AI platforms."""
    data = _get_cross_source(brand_id, days)
    return {
        "brand_id":               brand_id,
        "days":                   days,
        "cross_platform_queries": data.get("cross_platform_queries", []),
        "category_performance":   data.get("category_performance", []),
    }


@mcp.tool()
def compare_competitors(brand_id: int, days: int = 7) -> dict:
    """Compare the brand's AI visibility against its competitors."""
    data = _get_cross_source(brand_id, days)
    return {
        "brand_id":             brand_id,
        "days":                 days,
        "competitor_data":      data.get("competitor_data", {}),
        "radar_metrics":        data.get("radar_metrics", {}),
        "platform_competitors": data.get("platform_specific_competitors", {}),
    }


@mcp.tool()
def ask_guzu(brand_id: int, question: str, days: int = 7) -> dict:
    """Ask a natural language question about a brand's AI visibility."""
    data = _get_cross_source(brand_id, days)
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


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)


# ── NEW TOOL: analyze_brand ───────────────────────────────────────────────────
@mcp.tool()
def analyze_brand(website_url: str, geography: str = "Global", language: str = "en") -> dict:
    """
    Analyze a website and generate a brand profile for AI visibility tracking.

    This is Step 1 of brand setup. It scrapes the website, identifies the brand's
    offers, competitors, and generates tracking queries. Returns a profile payload
    that you can review and then pass to save_brand_tracking to start tracking.

    Args:
        website_url: Full URL of the website (e.g. "https://example.com")
        geography:   Target geography for tracking (e.g. "Global", "United States", "Singapore")
        language:    Language code (e.g. "en", "fr", "de")
    """
    api_key = _api_key_var.get()
    if not api_key:
        raise ValueError("No API key found.")

    r = httpx.post(
        f"{GUZU_BASE_URL}/api/analyze-website",
        json={"website_url": website_url, "target_geography": geography, "language": language},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60
    )
    if r.status_code == 401:
        raise ValueError("Invalid or expired API key")
    r.raise_for_status()
    data = r.json()

    analysis = data.get("analysis", {})

    # Apply same limits as the internal plugin
    profile = analysis.get("profile", {})
    competitors = analysis.get("competitors", {}).get("competitors", [])[:5]
    profile["competitors"] = competitors

    tracking = analysis.get("tracking_questions", {})
    tracking["brand_discovery"] = tracking.get("brand_discovery", [])[:2]
    tracking["offers"] = tracking.get("offers", [])[:3]
    for offer in tracking.get("offers", []):
        offer["category_discovery"] = offer.get("category_discovery", [])[:2]

    return {
        "website_url":        website_url,
        "source":             "mcp",
        "profile":            profile,
        "tracking_questions": tracking,
        "note":               "Review the profile and tracking_questions, then call save_brand_tracking to start tracking."
    }


# ── NEW TOOL: save_brand_tracking ─────────────────────────────────────────────
@mcp.tool()
def save_brand_tracking(
    website_url: str,
    profile: dict,
    tracking_questions: dict
) -> dict:
    """
    Save a brand for AI visibility tracking. This is Step 2 of brand setup.

    Pass the profile and tracking_questions returned by analyze_brand
    (optionally edited). Returns a brand_id you can use with all other tools.

    Args:
        website_url:         The website URL being tracked
        profile:             Brand profile from analyze_brand
        tracking_questions:  Tracking queries from analyze_brand
    """
    api_key = _api_key_var.get()
    if not api_key:
        raise ValueError("No API key found.")

    payload = {
        "website_url":        website_url,
        "source":             "mcp",
        "profile":            profile,
        "tracking_questions": tracking_questions,
    }

    r = httpx.post(
        f"{GUZU_BASE_URL}/api/save-brand-setup",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30
    )
    if r.status_code == 401:
        raise ValueError("Invalid or expired API key")
    r.raise_for_status()
    data = r.json()

    brand_id = data.get("brand_id")
    return {
        "brand_id":   brand_id,
        "website_url": website_url,
        "message":    f"Brand saved successfully. Use brand_id={brand_id} with get_visibility_score and other tools.",
    }
