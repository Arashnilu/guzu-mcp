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

from starlette.responses import JSONResponse

class ApiKeyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode()
            custom = headers.get(b"x-guzu-api-key", b"").decode()

            api_key = ""
            if auth.lower().startswith("bearer gzu_"):
                api_key = auth[7:]
            elif custom.startswith("gzu_"):
                api_key = custom

            path = scope.get("path", "")
            if path == "/sse" and not api_key:
                response = JSONResponse(
                    {"error": "API key required. Pass X-Guzu-Api-Key header."},
                    status_code=401
                )
                await response(scope, receive, send)
                return

            token = _api_key_var.set(api_key)
            try:
                await self.app(scope, receive, send)
            finally:
                _api_key_var.reset(token)
        else:
            await self.app(scope, receive, send)

app.add_middleware(ApiKeyMiddleware)


# ── Shared helpers ────────────────────────────────────────────────────────────
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


# Which AI platforms expose full gap/mention data (vs citation-frequency only)
_RICH_GAP_SOURCES = {"chatgpt", "ai_overview"}
_ALL_SOURCES = ["chatgpt", "perplexity", "gemini", "ai_overview", "grok", "claude"]


def _fetch_landscape(brand_id: int, source: str, days: int) -> dict:
    """Fetch the citation-landscape for a single source. Returns {} on 404/no-data."""
    api_key = _api_key_var.get()
    if not api_key:
        raise ValueError("No API key found. Connect with X-Guzu-Api-Key header.")
    r = httpx.get(
        f"{GUZU_BASE_URL}/api/{source}/citation-landscape",
        params={"brand_id": brand_id, "days": days},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30
    )
    if r.status_code == 401:
        raise ValueError("Invalid or expired API key")
    if r.status_code == 403:
        raise ValueError("Brand not found or does not belong to this account")
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json().get("data", {})


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_visibility_score(brand_id: int, days: int = 7) -> dict:
    """
    Get a brand's AI Visibility Score — how visible the brand is across AI
    platforms (ChatGPT, Perplexity, Gemini, AI Overview).

    Returns the AI Visibility Index, total citations and mentions, the brand's
    market position vs. competitors, and a per-platform breakdown showing which
    AI platforms cite/mention the brand most. This single tool answers
    "how visible am I?", "which platform am I strongest on?", and
    "what's my market position?".

    Requires a brand that has finished analyzing (see check_analyzing_progress).

    Args:
        brand_id: The brand ID from your Guzu account
        days:     Lookback window in days (default 7)
    """
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
        "platforms":           data.get("platform_comparison", []),
    }


@mcp.tool()
def get_results_by_prompt(brand_id: int, days: int = 7) -> dict:
    """
    Get the brand's AI-visibility results broken down by individual prompt
    (the tracked queries), plus performance grouped by category.

    Use this to answer "which specific prompts/questions does my brand show up
    on, and which ones is it missing from?" Each entry shows how the brand
    performed for that prompt across the AI platforms.

    Requires a brand that has finished analyzing (see check_analyzing_progress).

    Args:
        brand_id: The brand ID from your Guzu account
        days:     Lookback window in days (default 7)
    """
    data = _get_cross_source(brand_id, days)
    return {
        "brand_id":               brand_id,
        "days":                   days,
        "results_by_prompt":      data.get("cross_platform_queries", []),
        "category_performance":   data.get("category_performance", []),
    }


@mcp.tool()
def compare_competitors(brand_id: int, days: int = 7) -> dict:
    """
    Compare the brand's AI visibility against its tracked competitors.

    Returns the competitor ranking (where the brand sits vs. rivals), overall
    market position, radar metrics, and platform-specific competitor rankings
    (who leads on each AI platform). Use this to answer "who beats me in AI
    answers?" and "where do I rank against competitors?".

    Requires a brand that has finished analyzing (see check_analyzing_progress).

    Args:
        brand_id: The brand ID from your Guzu account
        days:     Lookback window in days (default 7)
    """
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
    """
    Ask a natural-language question about a brand's AI visibility. Gathers the
    most relevant visibility data for the brand and returns it so you can answer
    the question with specific numbers and actionable insight.

    Use this for open-ended questions like "why is my visibility low?" or
    "what should I focus on to improve?".

    Requires a brand that has finished analyzing (see check_analyzing_progress).

    Args:
        brand_id: The brand ID from your Guzu account
        question: The user's natural-language question
        days:     Lookback window in days (default 7)
    """
    data = _get_cross_source(brand_id, days)
    stats   = data.get("summary_stats", {})
    comp    = data.get("competitor_data", {})
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
            "top_queries":         queries[:10] if queries else [],
            "competitor_ranking":  comp.get("overall_ranking", [])[:5],
        },
        "note": "Use the data above to answer the question with specific numbers and actionable insights."
    }


# ── Setup pipeline: prepare_brand → start_analyzing → check_analyzing_progress ──

@mcp.tool()
def prepare_brand(website_url: str, geography: str = "Global", language: str = "en") -> dict:
    """
    STEP 1 of brand setup. Scan a website and build a draft AI-visibility
    tracking profile for review. This does NOT start tracking yet — it fetches
    information about the website so the user can review and edit the offers,
    competitors, and prompts before committing.

    It returns: the brand profile (name, type, value propositions), priority
    offers, competitors, and a set of tracking prompts (the questions Guzu will
    later ask the AI platforms about this brand).

    IMPORTANT — after calling this tool, you MUST:
    1. Display ALL of these sections clearly to the user:
       - Brand profile (name, type, value propositions)
       - Priority offers (list each offer name)
       - Competitors (name, domain, competes_with)
       - Tracking prompts, broken down as:
           * Brand discovery queries
           * Branded verification queries
           * Per-offer: category discovery queries
           * Per-offer: brand offer review queries
    2. Ask: "Would you like to start analyzing these as-is, or review and edit
       the offers, competitors, and prompts first?"
    3. If they want to edit — walk them through offers, then competitors, then
       prompts, applying their changes to the returned data.
    4. Once confirmed — call start_analyzing with the final (possibly edited)
       profile and tracking_questions.

    BEFORE calling this tool: if the user has not EXPLICITLY stated the target
    geography and language, you MUST ask them first. Do NOT infer or guess
    geography or language from the URL, domain name, currency, or page path.
    Ask the user "What target geography and language should I track this brand
    for?" and wait for their answer before calling this tool.   

    Args:
        website_url: Full URL of the website (e.g. "https://example.com")
        geography:   Target geography (e.g. "Global", "United States", "Singapore")
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
    if r.status_code == 429:
        body = r.json()
        raise ValueError(
            f"OUT OF CREDITS — not a rate limit, do NOT retry. "
            f"Preparing a brand costs {body.get('credits_needed', 25)} credits but the account "
            f"only has {body.get('credits_available', 0)}. "
            f"Tell the user to top up at guzu.ai/mcp/dashboard. Do not retry until they add credits."
        )
    r.raise_for_status()
    data = r.json()

    analysis = data.get("analysis", {})

    profile = analysis.get("profile", {})
    competitors = analysis.get("competitors", {}).get("competitors", [])[:5]
    profile["competitors"] = competitors

    tracking = analysis.get("tracking_questions", {})
    tracking["brand_discovery"]      = tracking.get("brand_discovery", [])[:6]
    tracking["branded_verification"] = tracking.get("branded_verification", [])[:6]
    tracking["offers"]               = tracking.get("offers", [])[:4]
    for offer in tracking.get("offers", []):
        offer["category_discovery"]  = offer.get("category_discovery", [])[:6]
        offer["brand_offer_review"]  = offer.get("brand_offer_review", [])[:6]

    return {
        "website_url":        website_url,
        "source":             "mcp",
        "profile":            profile,
        "tracking_questions": tracking,
        "INSTRUCTIONS":       (
            "Display ALL sections above to the user (profile, offers, competitors, AND all prompts). "
            "Then ask: 'Start analyzing as-is, or review and edit first?' "
            "If edit: walk through offers -> competitors -> prompts. "
            "Then call start_analyzing with the final data."
        )
    }


@mcp.tool()
def start_analyzing(
    website_url: str,
    profile: dict,
    tracking_questions: dict
) -> dict:
    """
    STEP 2 of brand setup. Save the prepared brand and START ANALYZING it.

    "Analyzing" means Guzu takes each tracking prompt and asks it to the AI
    platforms your account covers (ChatGPT, Perplexity, Gemini, AI Overview),
    then records whether the brand is cited or mentioned, which competitors are
    cited, and which third-party domains the AI relies on. This is the step that
    produces all the visibility data the other tools read.

    You MUST have called prepare_brand first — pass the profile and
    tracking_questions it returned (optionally edited by the user). It returns a
    brand_id used by all the reporting tools.

    After calling this, tell the user analysis is running (it takes ~10-12
    minutes) and that they can check progress with
    check_analyzing_progress(brand_id).

    Args:
        website_url:         The website URL being tracked
        profile:             Brand profile from prepare_brand
        tracking_questions:  Tracking prompts from prepare_brand
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
    if r.status_code == 429:
        body = r.json()
        prompts = body.get('prompts')
        affordable = body.get('affordable_prompts')
        if prompts is not None and affordable is not None:
            to_remove = max(0, prompts - affordable)
            detail = (
                f"This brand has {prompts} prompts ({body.get('credits_needed', 0)} credits). "
                f"The account has {body.get('credits_available', 0)} credits — enough for {affordable} prompts. "
                f"To start now, remove {to_remove} prompt(s), or top up at guzu.ai/mcp/dashboard. "
            )
        else:
            detail = (
                f"You need {body.get('credits_needed', 0)} credits but only have "
                f"{body.get('credits_available', 0)}. Top up at guzu.ai/mcp/dashboard. "
            )
        raise ValueError(
            "OUT OF CREDITS — not a rate limit, do NOT retry. " + detail +
            "Do not retry until the user reduces prompts or adds credits."
        )
    if r.status_code == 403:
        body = r.json()
        raise ValueError(
            f"Cannot start analyzing: {body.get('error', 'limit reached or not allowed')}. "
            f"Do NOT retry — this is a permanent rejection until the user resolves it."
        )
    r.raise_for_status()
    data = r.json()

    brand_id = data.get("brand_id")
    note = data.get("note")  # may carry a 105-prompt cap notice
    result = {
        "brand_id":    brand_id,
        "website_url": website_url,
        "prompts_saved": data.get("prompts_saved"),
        "message":     f"Analysis started. brand_id={brand_id}.",
        "INSTRUCTIONS": (
            f"Tell the user: 'Analysis started! brand_id={brand_id}. "
            "Guzu is now running your prompts across the AI platforms your account covers. "
            "This usually takes 10-12 minutes. "
            f"Check progress anytime with check_analyzing_progress(brand_id={brand_id}).'"
        )
    }
    if note:
        result["cap_note"] = note
    return result


@mcp.tool()
def check_analyzing_progress(brand_id: int) -> dict:
    """
    Check how far along the analysis is for a brand — which AI platforms have
    finished collecting data and which are still processing.

    Show the user exactly which platforms are done and which are pending. Do NOT
    estimate how long the remaining platforms will take — you don't know. If
    platforms are still pending, ask the user to check again shortly.

    When everything is ready, you can call get_visibility_score,
    compare_competitors, get_results_by_prompt, and gap_analysis to build the
    full report.

    Args:
        brand_id: The brand ID returned by start_analyzing
    """
    api_key = _api_key_var.get()
    if not api_key:
        raise ValueError("No API key found.")

    r = httpx.get(
        f"{GUZU_BASE_URL}/api/brand/status/{brand_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15
    )
    if r.status_code == 401:
        raise ValueError("Invalid or expired API key")
    r.raise_for_status()
    return r.json()


# ── gap_analysis (the citation & domain gap tool) ──────────────────────────────

def _shape_landscape(data: dict) -> dict:
    """Trim one source's landscape payload into a compact, structured view."""
    if not data:
        return {}
    source = data.get("source")
    summary = data.get("summary", {}) or {}
    q_total = summary.get("queries_total", 0) or 0
    cited = summary.get("brand_cited", 0) or 0
    cited_pct = round((cited / q_total) * 100) if q_total else 0

    # Domain leaderboard — keep the most useful fields, opportunities first
    domains = data.get("domain_opportunities", []) or []
    leaderboard = [{
        "domain":        d.get("domain"),
        "content_type":  d.get("content_type"),
        "cite_rate":     d.get("cite_rate"),
        "queries_cited": d.get("queries_cited"),
        "queries_seen":  d.get("queries_seen"),
        "is_opportunity": d.get("is_opportunity"),
        "mentions_you":   d.get("mentions_you"),
        "mentions_rivals": d.get("mentions_rivals"),
        "sample_url":    d.get("sample_url"),
        "sample_title":  d.get("sample_title"),
    } for d in domains]

    return {
        "source":               source,
        "has_gap_data":         source in _RICH_GAP_SOURCES,
        "summary": {
            "queries_total":         q_total,
            "brand_cited":           cited,
            "brand_cited_pct":       cited_pct,
            "brand_not_cited":       summary.get("brand_not_cited", 0),
            "gap_pages":             summary.get("gap_pages", 0),
            "content_type_breakdown": summary.get("content_type_breakdown", []),
        },
        "domain_leaderboard":   leaderboard,
        # per-query is included only in single-source mode (see gap_analysis)
        "queries":              data.get("queries", []),
    }


@mcp.tool()
def gap_analysis(brand_id: int, source: str = "all", days: int = 7) -> dict:
    """
    Find where a brand is MISSING from AI answers — the citation & domain gap
    analysis. This is the most actionable visibility tool.

    For each AI platform it shows: how often the brand is cited vs not, the
    overall content-type mix of what the AI cites (Blog, Listicle, Forum,
    Other/directories, etc.), and a ranked leaderboard of the domains the AI
    relies on — flagging "opportunity" domains that get cited but where the
    brand is absent (and, on ChatGPT and AI Overview, which of those mention
    rivals but not the brand).

    PLATFORM COVERAGE:
    - source="all" (default): analyzes every AI platform the account covers and
      returns them keyed by platform. Best for a complete picture.
    - source="chatgpt" | "perplexity" | "gemini" | "ai_overview" | "grok" |
      "claude": just that one platform, WITH full per-query breakdown.
    - Full gap/mention detail (mentions-you, mentions-rivals, gap pages) is only
      available for ChatGPT and AI Overview (has_gap_data=true). Other platforms
      return accurate citation frequency but not the you-vs-rival gap detail —
      tell the user this if they ask about gaps on those platforms.

    AFTER returning the data, proactively offer these follow-ups (you derive them
    from the data already returned — do NOT call another tool):
      1. ACTION PLAN — prioritized recommendations: which opportunity domains and
         content types to target first (rank by cite_rate, whether rivals are
         cited there, and gap status).
      2. PER-PROMPT GAP BREAKDOWN — walk through each prompt (the `queries`
         array, available in single-source mode): where the brand is cited, where
         rivals are cited, and the specific gap pages for that prompt. If the user
         wants this and you fetched source="all", re-run gap_analysis for the one
         platform they care about to get the per-query detail.
      3. OFF-PAGE STRATEGY vs CONTENT STRATEGY — split the opportunity domains by
         content_type:
           * CONTENT STRATEGY (work done ON the client's own site): opportunities
             where the cited source is article/content the client could publish
             themselves — content_type in {Blog, Listicle, News/Editorial, Video}.
             The play: write that content on their own site to earn the citation.
           * OFF-PAGE STRATEGY (work done on THIRD-PARTY sites): opportunities
             where the cited source is a third-party listing/mention the client
             can't self-publish — content_type in {Other, Forum, Social,
             LinkedIn}. The play: get listed / mentioned / cited on those sources
             (directories, profiles, outreach).

    Args:
        brand_id: The brand ID from your Guzu account
        source:   "all" (default) or one of chatgpt, perplexity, gemini,
                  ai_overview, grok, claude
        days:     Lookback window in days (default 7)
    """
    source = (source or "all").strip().lower()
    valid = set(_ALL_SOURCES) | {"all"}
    if source not in valid:
        raise ValueError(
            f"Invalid source '{source}'. Use 'all' or one of: {', '.join(_ALL_SOURCES)}"
        )

    followups = {
        "action_plan": "Prioritized recommendations from the opportunity domains and content-type mix.",
        "per_prompt_gap_breakdown": "Gap detail for each individual prompt (single-source mode has full per-query data).",
        "off_page_vs_content_strategy": "Split opportunities into content-strategy (publish on own site) vs off-page-strategy (get listed/mentioned on third-party sites).",
    }

    if source != "all":
        data = _fetch_landscape(brand_id, source, days)
        shaped = _shape_landscape(data)
        if not shaped:
            return {
                "brand_id": brand_id,
                "source": source,
                "message": f"No analysis data for {source} yet. The brand may still be analyzing.",
            }
        shaped["brand_id"] = data.get("brand_id", brand_id)
        shaped["brand_name"] = data.get("brand_name")
        shaped["days"] = days
        shaped["available_followups"] = followups
        return shaped

    # source == "all": fetch each subscribed platform; tolerate missing ones.
    # We discover which platforms have data by trying them and skipping empties.
    results = {}
    for src in _ALL_SOURCES:
        try:
            data = _fetch_landscape(brand_id, src, days)
        except ValueError:
            raise  # auth/ownership errors should bubble up
        except Exception:
            continue
        if not data or not data.get("queries"):
            continue
        shaped = _shape_landscape(data)
        # In multi-platform mode, drop the heavy per-query array to keep the
        # response compact; per-query detail is available via single-source mode.
        shaped.pop("queries", None)
        shaped["per_query_available_via"] = f"gap_analysis(brand_id={brand_id}, source='{src}')"
        results[src] = shaped

    if not results:
        return {
            "brand_id": brand_id,
            "source": "all",
            "message": "No analysis data available yet on any platform. The brand may still be analyzing — check_analyzing_progress(brand_id).",
        }

    return {
        "brand_id": brand_id,
        "days": days,
        "platforms_analyzed": list(results.keys()),
        "by_platform": results,
        "note": (
            "Full gap/mention detail is available for ChatGPT and AI Overview "
            "(has_gap_data=true). Other platforms show accurate citation frequency "
            "but not you-vs-rival gap detail. Per-prompt breakdown is omitted here "
            "for brevity — re-run with a single source to get it."
        ),
        "available_followups": followups,
    }


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
