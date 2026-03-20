"""
data_sources.py - Centralized API Client Functions
====================================================
All external data source fetchers used by the multi-agent pipeline.

Sources by category:
  MACRO:       FRED, Treasury.gov, IMF, World Bank, ECB
  DEFI:        DefiLlama, CoinGecko, GeckoTerminal
  RWA:         RWA.xyz, protocol-specific APIs
  NEWS:        GDELT, Alpha Vantage News, NewsAPI
  SOCIAL:      Reddit, Bluesky
  TRADE:       UN Comtrade

All functions return dicts/lists and gracefully return empty results
if API keys are missing or endpoints are unreachable.
"""

import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# --- API Keys ---
FRED_KEY = os.getenv("FRED_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")

# --- Base URLs ---
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEFILLAMA_BASE = "https://api.llama.fi"
GECKO_TERMINAL_BASE = "https://api.geckoterminal.com/api/v2"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
NEWS_API_BASE = "https://newsapi.org/v2"
WORLD_BANK_BASE = "https://api.worldbank.org/v2"
IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"
ECB_BASE = "https://data-api.ecb.europa.eu/service/data"
COMTRADE_BASE = "https://comtradeapi.un.org/public/v1/preview"
BLUESKY_BASE = "https://public.api.bsky.app/xrpc"
RWA_XYZ_BASE = "https://api.rwa.xyz/v1"


def _http_get(url: str, params: dict = None, timeout: int = 15,
              headers: dict = None) -> Optional[dict]:
    """Generic HTTP GET with error handling."""
    try:
        hdrs = {"User-Agent": "RWAAgent/2.0"}
        if headers:
            hdrs.update(headers)
        resp = requests.get(url, params=params, timeout=timeout, headers=hdrs)
        if resp.status_code in (400, 403, 404, 429):
            logger.debug("[data_sources] HTTP %d from %s", resp.status_code, url)
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("[data_sources] %s: %s", url, e)
        return None


def _http_get_text(url: str, params: dict = None, timeout: int = 15) -> Optional[str]:
    """HTTP GET returning raw text (for XML endpoints)."""
    try:
        resp = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": "RWAAgent/2.0"})
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.debug("[data_sources] text %s: %s", url, e)
        return None


# ============================================================================
# MACRO SOURCES
# ============================================================================

def fetch_fred_series(series_id: str, limit: int = 10) -> list:
    """Fetch recent observations from FRED. Requires FRED_API_KEY."""
    if not FRED_KEY:
        return []
    data = _http_get(FRED_BASE, {
        "series_id": series_id, "api_key": FRED_KEY,
        "file_type": "json", "sort_order": "desc", "limit": str(limit),
    })
    if not data:
        return []
    obs = data.get("observations", [])
    results = []
    for o in obs:
        val = o.get("value", ".")
        if val not in (".", "", None):
            results.append({"date": o.get("date"), "value": float(val)})
    return results


def fetch_fred_latest(series_id: str) -> Optional[float]:
    """Fetch single latest value from FRED."""
    obs = fetch_fred_series(series_id, limit=1)
    return obs[0]["value"] if obs else None


def fetch_treasury_yields() -> dict:
    """Fetch US Treasury daily yield curve from Treasury.gov XML."""
    year = datetime.now().year
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/"
        f"interest-rates/pages/xml?data=daily_treasury_yield_curve"
        f"&field_tdr_date_value={year}"
    )
    text = _http_get_text(url)
    if not text:
        return {}

    result = {}
    try:
        root = ET.fromstring(text)
        ns_d = "http://schemas.microsoft.com/ado/2007/08/dataservices"
        ns_m = "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
        ns_atom = "http://www.w3.org/2005/Atom"

        entries = root.findall(f"{{{ns_atom}}}entry") or root.findall("entry")
        if not entries:
            return result

        latest = entries[-1]
        props = latest.find(f".//{{{ns_m}}}properties")
        if props is None:
            props = latest.find(".//properties")
        if props is None:
            return result

        field_map = {
            "BC_1MONTH": "yield_1m", "BC_3MONTH": "yield_3m",
            "BC_6MONTH": "yield_6m", "BC_1YEAR": "yield_1y",
            "BC_2YEAR": "yield_2y", "BC_5YEAR": "yield_5y",
            "BC_10YEAR": "yield_10y", "BC_30YEAR": "yield_30y",
            "NEW_DATE": "date",
        }
        for xml_field, key in field_map.items():
            el = props.find(f"{{{ns_d}}}{xml_field}")
            if el is None:
                el = props.find(xml_field)
            if el is not None and el.text:
                try:
                    result[key] = el.text[:10] if key == "date" else float(el.text)
                except ValueError:
                    pass
    except Exception as e:
        logger.debug("[data_sources] Treasury XML parse: %s", e)
    return result


def fetch_world_bank_indicator(indicator: str, country: str = "US",
                                date_range: str = "2020:2026") -> list:
    """
    Fetch World Bank indicator data.
    Examples: NY.GDP.MKTP.KD.ZG (GDP growth), FP.CPI.TOTL.ZG (inflation)
    """
    url = f"{WORLD_BANK_BASE}/country/{country}/indicator/{indicator}"
    data = _http_get(url, {"format": "json", "date": date_range, "per_page": "20"})
    if not data or not isinstance(data, list) or len(data) < 2:
        return []
    return [
        {"date": entry.get("date"), "value": entry.get("value"),
         "country": entry.get("country", {}).get("value")}
        for entry in data[1]
        if entry.get("value") is not None
    ]


def fetch_imf_indicators(dataset: str = "FM", indicator: str = "FPOLM_PA",
                          countries: list = None) -> dict:
    """
    Fetch IMF DataMapper indicators.
    FM/FPOLM_PA = monetary policy rate
    NGDP_RPCH = real GDP growth
    PCPIPCH = consumer price inflation
    """
    countries = countries or ["USA", "GBR", "DEU", "JPN", "CHN"]
    url = f"{IMF_BASE}/{dataset}/{indicator}"
    data = _http_get(url)
    if not data or "values" not in data:
        return {}
    values = data.get("values", {}).get(indicator, {})
    result = {}
    for c in countries:
        if c in values:
            series = values[c]
            latest_year = max(series.keys()) if series else None
            if latest_year:
                result[c] = {"year": latest_year, "value": series[latest_year]}
    return result


def fetch_ecb_rates() -> dict:
    """Fetch ECB key interest rates from ECB Data Portal."""
    url = f"{ECB_BASE}/FM/M.U2.EUR.4F.KR.MRR_FR.LEV"
    data = _http_get(url, {"format": "jsondata", "lastNObservations": "5"})
    if not data:
        return {}
    try:
        series = data["dataSets"][0]["series"]
        key = list(series.keys())[0]
        obs = series[key]["observations"]
        latest_key = max(obs.keys())
        return {"ecb_main_rate": obs[latest_key][0], "source": "ECB"}
    except (KeyError, IndexError):
        return {}


def fetch_chicago_fed_nfci() -> Optional[float]:
    """Fetch Chicago Fed National Financial Conditions Index via FRED."""
    return fetch_fred_latest("NFCI")


def fetch_gdpnow() -> Optional[float]:
    """Fetch Atlanta Fed GDPNow estimate via FRED."""
    return fetch_fred_latest("GDPNOW")


# ============================================================================
# DEFI SOURCES
# ============================================================================

def fetch_defillama_protocols(top_n: int = 100) -> list:
    """Fetch top DeFi protocols by TVL from DefiLlama."""
    data = _http_get(f"{DEFILLAMA_BASE}/protocols")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "name": p.get("name"), "slug": p.get("slug"),
            "tvl": p.get("tvl", 0), "chain": p.get("chain"),
            "category": p.get("category"),
            "change_1d": p.get("change_1d"), "change_7d": p.get("change_7d"),
        }
        for p in data[:top_n]
    ]


def fetch_defillama_protocol(slug: str) -> Optional[dict]:
    """Fetch detailed protocol data from DefiLlama."""
    return _http_get(f"{DEFILLAMA_BASE}/protocol/{slug}")


def fetch_defillama_chains() -> list:
    """Fetch chain-level TVL data from DefiLlama."""
    data = _http_get(f"{DEFILLAMA_BASE}/v2/chains")
    if not data or not isinstance(data, list):
        return []
    return [
        {"name": c.get("name"), "tvl": c.get("tvl", 0),
         "tokenSymbol": c.get("tokenSymbol")}
        for c in data[:30]
    ]


def fetch_defillama_stablecoins() -> dict:
    """Fetch stablecoin market data from DefiLlama."""
    data = _http_get(f"https://stablecoins.llama.fi/stablecoins?includePrices=true")
    if not data:
        return {}
    pegged = data.get("peggedAssets", [])
    total_mcap = sum(
        p.get("circulating", {}).get("peggedUSD", 0) or 0
        for p in pegged[:20]
    )
    return {
        "total_stablecoin_mcap": total_mcap,
        "top_stablecoins": [
            {"name": p.get("name"), "symbol": p.get("symbol"),
             "mcap": p.get("circulating", {}).get("peggedUSD", 0)}
            for p in pegged[:10]
        ],
    }


def fetch_defillama_yields(pool_filter: str = None) -> list:
    """Fetch DeFi yield pools from DefiLlama."""
    data = _http_get("https://yields.llama.fi/pools")
    if not data or "data" not in data:
        return []
    pools = data["data"]
    if pool_filter:
        pools = [p for p in pools if pool_filter.lower() in
                 (p.get("project", "") + p.get("symbol", "")).lower()]
    return [
        {"pool": p.get("pool"), "project": p.get("project"),
         "symbol": p.get("symbol"), "tvl": p.get("tvlUsd", 0),
         "apy": p.get("apy", 0), "chain": p.get("chain")}
        for p in pools[:50]
    ]


def fetch_coingecko_market(token_ids: list = None, vs_currency: str = "usd",
                            per_page: int = 50) -> list:
    """Fetch market data from CoinGecko."""
    params = {
        "vs_currency": vs_currency, "order": "market_cap_desc",
        "per_page": str(per_page), "sparkline": "false",
        "price_change_percentage": "1h,24h,7d,30d",
    }
    if token_ids:
        params["ids"] = ",".join(token_ids)
    data = _http_get(f"{COINGECKO_BASE}/markets", params)
    if not data:
        return []
    return [
        {
            "id": t.get("id"), "symbol": t.get("symbol", "").upper(),
            "name": t.get("name"), "price": t.get("current_price", 0),
            "market_cap": t.get("market_cap", 0),
            "volume_24h": t.get("total_volume", 0),
            "change_24h": t.get("price_change_percentage_24h", 0),
            "change_7d": t.get("price_change_percentage_7d_in_currency", 0),
            "change_30d": t.get("price_change_percentage_30d_in_currency", 0),
        }
        for t in data
    ]


def fetch_coingecko_price_history(token_id: str, days: int = 90) -> list:
    """Fetch price history from CoinGecko. Returns list of [timestamp, price]."""
    data = _http_get(f"{COINGECKO_BASE}/coins/{token_id}/market_chart", {
        "vs_currency": "usd", "days": str(days), "interval": "daily",
    })
    if not data or "prices" not in data:
        return []
    return [[p[0], p[1]] for p in data["prices"]]


def fetch_gecko_terminal_pools(network: str = "eth", top_n: int = 20) -> list:
    """Fetch top DEX pools from GeckoTerminal."""
    data = _http_get(
        f"{GECKO_TERMINAL_BASE}/networks/{network}/trending_pools",
        {"page": "1"}
    )
    if not data or "data" not in data:
        return []
    return [
        {
            "name": p.get("attributes", {}).get("name"),
            "dex": p.get("relationships", {}).get("dex", {}).get("data", {}).get("id"),
            "volume_24h": p.get("attributes", {}).get("volume_usd", {}).get("h24"),
            "price_change_24h": p.get("attributes", {}).get("price_change_percentage", {}).get("h24"),
        }
        for p in data["data"][:top_n]
    ]


# ============================================================================
# RWA SOURCES  (Primary: DefiLlama RWA category — the live RWA universe)
# ============================================================================

# --- KYC Metadata from DefiLlama GitHub (protocols.ts) ---
# Cache for parsed KYC metadata: { defillama_protocol_id: { kyc, transferable, ... } }
_kyc_metadata_cache: dict = {}
_kyc_cache_timestamp: float = 0
_KYC_CACHE_TTL = 3600  # 1 hour

DEFILLAMA_RWA_PROTOCOLS_URL = (
    "https://raw.githubusercontent.com/DefiLlama/defillama-server/"
    "master/defi/src/rwa/protocols.ts"
)


def fetch_defillama_kyc_metadata() -> dict:
    """
    Fetch and parse DefiLlama's RWA protocol KYC metadata from GitHub.
    Source: defillama-server/defi/src/rwa/protocols.ts

    This is the SAME data DefiLlama uses for the 'Access Model' column
    (Permissionless / Permissioned) on their RWA dashboard.

    Returns dict: { protocol_id_str: { kyc: bool, transferable: bool, ... } }
    """
    global _kyc_metadata_cache, _kyc_cache_timestamp
    now = time.time()

    # Return cache if fresh
    if _kyc_metadata_cache and (now - _kyc_cache_timestamp) < _KYC_CACHE_TTL:
        return _kyc_metadata_cache

    text = _http_get_text(DEFILLAMA_RWA_PROTOCOLS_URL)
    if not text:
        logger.warning("[data_sources] Failed to fetch DefiLlama KYC metadata")
        return _kyc_metadata_cache  # return stale cache if available

    import re
    metadata = {}

    # Parse TypeScript object entries like: "2542": { ... kyc: true, transferable: true ... }
    # Pattern: "ID": { ... }
    block_pattern = re.compile(
        r'"(\d+)":\s*\{([^}]+)\}', re.DOTALL
    )

    for match in block_pattern.finditer(text):
        protocol_id = match.group(1)
        block = match.group(2)

        entry = {}
        for field in ["kyc", "transferable", "redeemable", "attestations",
                       "cexListed", "selfCustody"]:
            # Match field: true/false
            field_match = re.search(rf'{field}\s*:\s*(true|false)', block)
            if field_match:
                entry[field] = field_match.group(1) == "true"

        if entry:
            metadata[protocol_id] = entry

    if metadata:
        _kyc_metadata_cache = metadata
        _kyc_cache_timestamp = now
        logger.info(
            "[data_sources] Loaded KYC metadata for %d RWA protocols "
            "(permissionless: %d, kyc-required: %d)",
            len(metadata),
            sum(1 for m in metadata.values() if not m.get("kyc", True)),
            sum(1 for m in metadata.values() if m.get("kyc", True)),
        )

    return metadata


def get_access_model(protocol_id: str, kyc_metadata: dict = None) -> str:
    """
    Determine access model for a protocol.
    Returns: 'permissionless', 'permissioned', or 'unknown'
    """
    if kyc_metadata is None:
        kyc_metadata = fetch_defillama_kyc_metadata()

    meta = kyc_metadata.get(str(protocol_id))
    if not meta:
        return "unknown"

    if not meta.get("kyc", True):
        return "permissionless"
    return "permissioned"


# Asset-type classification heuristics (applied to DefiLlama RWA protocols)
_ASSET_TYPE_KEYWORDS = {
    "treasury": ["treasury", "tbill", "t-bill", "ustb", "buidl", "usyc",
                 "openeden", "superstate", "vaneck treasury", "thbill",
                 "ondo", "spiko", "sky rwa", "midas rwa"],
    "gold": ["gold", "xaum", "paxos gold", "tether gold", "comtech gold", "meld gold"],
    "credit": ["credit", "lending", "loan", "clearpool", "maple", "goldfinch",
               "centrifuge", "pareto", "csigma", "figure", "securitize",
               "apollo", "hamilton lane", "nest credit", "kea credit"],
    "real_estate": ["real estate", "realt", "lofty", "propbase", "estate protocol",
                    "binaryx", "vesta equity", "raac", "realtyx", "chateau"],
    "equity": ["stock", "equity", "xstocks", "dinari", "backed"],
    "insurance": ["insurance"],
    "stablecoin_rwa": ["usd0", "frax usd", "usdtb", "stusdt", "fiusd", "usd ai"],
    "yield": ["yield", "pendle"],
    "commodity": ["uranium", "commodity"],
}


def _classify_rwa_asset_type(name: str, description: str = "",
                              category: str = "") -> str:
    """Classify an RWA protocol into an asset type based on name/description."""
    text = f"{name} {description} {category}".lower()
    for asset_type, keywords in _ASSET_TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return asset_type
    return "other"


def fetch_rwa_universe(min_tvl_usd: float = 1_000_000,
                        access_filter: str = None) -> list:
    """
    Fetch the LIVE RWA asset universe from DefiLlama.
    This is the SINGLE SOURCE OF TRUTH for all assets in the pipeline.

    Args:
        min_tvl_usd: Minimum TVL to include.
        access_filter: Optional filter —
            'permissionless' = only non-KYC tokens,
            'permissioned'   = only KYC-required tokens,
            None             = all tokens.

    Returns all RWA, RWA Lending, and Treasury Manager protocols with TVL >= min_tvl_usd.
    Each entry includes: name, slug, tvl, chain, chains, category, asset_type,
    gecko_id, symbol, description, change_1d, change_7d, mcap, kyc, access_model.
    """
    data = _http_get(f"{DEFILLAMA_BASE}/protocols")
    if not data or not isinstance(data, list):
        logger.warning("[data_sources] Failed to fetch DefiLlama protocols")
        return []

    # Fetch KYC metadata from DefiLlama GitHub
    kyc_metadata = fetch_defillama_kyc_metadata()

    rwa_categories = {"rwa", "rwa lending", "treasury manager"}
    rwa_protocols = [
        p for p in data
        if (p.get("category", "") or "").lower() in rwa_categories
        and (p.get("tvl", 0) or 0) >= min_tvl_usd
    ]

    universe = []
    for p in sorted(rwa_protocols, key=lambda x: x.get("tvl", 0) or 0, reverse=True):
        name = p.get("name", "")
        desc = p.get("description", "") or ""
        cat = p.get("category", "") or ""
        protocol_id = str(p.get("id", ""))
        asset_type = _classify_rwa_asset_type(name, desc, cat)

        # KYC classification from DefiLlama protocols.ts
        access = get_access_model(protocol_id, kyc_metadata)
        kyc_meta = kyc_metadata.get(protocol_id, {})
        requires_kyc = kyc_meta.get("kyc", None)  # None = unknown

        # Apply access filter if requested
        if access_filter:
            if access_filter == "permissionless" and access != "permissionless":
                continue
            elif access_filter == "permissioned" and access != "permissioned":
                continue

        universe.append({
            "name": name,
            "slug": p.get("slug", ""),
            "symbol": (p.get("symbol", "") or "").upper(),
            "tvl": p.get("tvl", 0) or 0,
            "mcap": p.get("mcap") or 0,
            "chain": p.get("chain", ""),
            "chains": p.get("chains", []),
            "category": cat,
            "asset_type": asset_type,
            "gecko_id": p.get("gecko_id") or "",
            "description": desc[:200],
            "url": p.get("url", ""),
            "audits": p.get("audits") or 0,
            "change_1d": p.get("change_1d"),
            "change_7d": p.get("change_7d"),
            # KYC / Access Model fields
            "kyc": requires_kyc,
            "transferable": kyc_meta.get("transferable"),
            "access_model": access,
        })

    logger.info(
        "[data_sources] RWA universe: %d protocols (filter=%s), total TVL $%.1fB",
        len(universe),
        access_filter or "all",
        sum(a["tvl"] for a in universe) / 1e9,
    )
    return universe


def fetch_rwa_xyz_overview() -> dict:
    """
    Fetch RWA market overview. Uses DefiLlama RWA category as primary source.
    """
    universe = fetch_rwa_universe(min_tvl_usd=0)
    total_tvl = sum(a["tvl"] for a in universe)

    # Group by asset_type
    by_type = {}
    for a in universe:
        t = a["asset_type"]
        by_type.setdefault(t, {"count": 0, "tvl": 0})
        by_type[t]["count"] += 1
        by_type[t]["tvl"] += a["tvl"]

    return {
        "total_rwa_tvl": total_tvl,
        "asset_count": len(universe),
        "asset_type_breakdown": by_type,
        "assets": universe[:50],
    }


def fetch_rwa_protocol_detail(slug: str) -> Optional[dict]:
    """Fetch detailed protocol data from DefiLlama for a specific RWA protocol."""
    return fetch_defillama_protocol(slug)


# ============================================================================
# NEWS / SENTIMENT SOURCES
# ============================================================================

def fetch_gdelt_articles(query: str, max_records: int = 50,
                          timespan: str = "7d") -> list:
    """
    Fetch articles from GDELT DOC API.
    Free, no key required. Returns article metadata + tone scores.
    """
    data = _http_get(GDELT_DOC_API, {
        "query": query,
        "mode": "ArtList",
        "maxrecords": str(max_records),
        "format": "json",
        "timespan": timespan,
    })
    if not data or "articles" not in data:
        return []
    return [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": a.get("domain", ""),
            "date": a.get("seendate", ""),
            "language": a.get("language", ""),
            "tone": a.get("tone", 0),  # GDELT tone: negative=bad, positive=good
            "socialimage": a.get("socialimage", ""),
        }
        for a in data["articles"][:max_records]
    ]


def fetch_gdelt_tone(query: str, timespan: str = "30d") -> dict:
    """
    Fetch GDELT tone/volume timeline for a query.
    Returns aggregate sentiment metrics.
    """
    data = _http_get(GDELT_DOC_API, {
        "query": query,
        "mode": "TimelineTone",
        "format": "json",
        "timespan": timespan,
    })
    if not data or "timeline" not in data:
        return {}
    timeline = data["timeline"]
    if not timeline or not timeline[0].get("data"):
        return {}
    points = timeline[0]["data"]
    tones = [p.get("value", 0) for p in points if p.get("value") is not None]
    if not tones:
        return {}
    return {
        "avg_tone": round(sum(tones) / len(tones), 3),
        "min_tone": round(min(tones), 3),
        "max_tone": round(max(tones), 3),
        "latest_tone": round(tones[-1], 3),
        "data_points": len(tones),
        "trend": "improving" if len(tones) >= 2 and tones[-1] > tones[0] else "declining",
    }


def fetch_alpha_vantage_news(tickers: str = None, topics: str = None,
                              limit: int = 20) -> list:
    """
    Fetch news + sentiment from Alpha Vantage.
    Requires ALPHA_VANTAGE_API_KEY.
    tickers: comma-separated (e.g. "CRYPTO:BTC,CRYPTO:ETH")
    topics: e.g. "blockchain", "financial_markets"
    """
    if not ALPHA_VANTAGE_KEY:
        return []
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": ALPHA_VANTAGE_KEY,
        "limit": str(limit),
    }
    if tickers:
        params["tickers"] = tickers
    if topics:
        params["topics"] = topics
    data = _http_get(ALPHA_VANTAGE_BASE, params)
    if not data or "feed" not in data:
        return []
    return [
        {
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "time_published": a.get("time_published", ""),
            "overall_sentiment_score": a.get("overall_sentiment_score", 0),
            "overall_sentiment_label": a.get("overall_sentiment_label", ""),
            "ticker_sentiment": a.get("ticker_sentiment", []),
        }
        for a in data["feed"][:limit]
    ]


def fetch_newsapi_articles(query: str, language: str = "en",
                            sort_by: str = "relevancy",
                            page_size: int = 20) -> list:
    """Fetch articles from NewsAPI. Requires NEWS_API_KEY."""
    if not NEWS_API_KEY:
        return []
    data = _http_get(f"{NEWS_API_BASE}/everything", {
        "q": query, "language": language, "sortBy": sort_by,
        "pageSize": str(page_size), "apiKey": NEWS_API_KEY,
    })
    if not data or "articles" not in data:
        return []
    return [
        {
            "title": a.get("title", ""),
            "source": a.get("source", {}).get("name", ""),
            "published_at": a.get("publishedAt", ""),
            "description": a.get("description", ""),
            "url": a.get("url", ""),
        }
        for a in data["articles"][:page_size]
    ]


# ============================================================================
# SOCIAL SOURCES
# ============================================================================

def fetch_bluesky_posts(query: str, limit: int = 25) -> list:
    """
    Search Bluesky public API for posts matching query.
    No auth required for public search.
    """
    data = _http_get(f"{BLUESKY_BASE}/app.bsky.feed.searchPosts", {
        "q": query, "limit": str(limit),
    })
    if not data or "posts" not in data:
        return []
    return [
        {
            "text": p.get("record", {}).get("text", ""),
            "author": p.get("author", {}).get("handle", ""),
            "created_at": p.get("record", {}).get("createdAt", ""),
            "like_count": p.get("likeCount", 0),
            "repost_count": p.get("repostCount", 0),
        }
        for p in data["posts"][:limit]
    ]


def fetch_reddit_sentiment(subreddit: str = "cryptocurrency",
                            query: str = None, limit: int = 25) -> list:
    """
    Fetch Reddit posts. Uses PRAW if credentials available,
    falls back to public JSON API.
    """
    if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
        try:
            import praw
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent="RWAAgent/2.0",
            )
            sub = reddit.subreddit(subreddit)
            posts = sub.search(query, limit=limit) if query else sub.hot(limit=limit)
            return [
                {
                    "title": p.title, "score": p.score,
                    "num_comments": p.num_comments,
                    "created_utc": p.created_utc,
                    "selftext": p.selftext[:300] if p.selftext else "",
                }
                for p in posts
            ]
        except Exception as e:
            logger.debug("[data_sources] PRAW: %s", e)

    # Public JSON fallback
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    if not query:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    params = {"q": query, "limit": str(limit), "sort": "relevance", "t": "week"} if query else {"limit": str(limit)}
    data = _http_get(url, params)
    if not data or "data" not in data:
        return []
    return [
        {
            "title": p["data"].get("title", ""),
            "score": p["data"].get("score", 0),
            "num_comments": p["data"].get("num_comments", 0),
            "created_utc": p["data"].get("created_utc", 0),
            "selftext": p["data"].get("selftext", "")[:300],
        }
        for p in data["data"].get("children", [])[:limit]
    ]


# ============================================================================
# TRADE DATA
# ============================================================================

def fetch_un_comtrade(reporter: str = "842", partner: str = "0",
                       commodity_code: str = "TOTAL",
                       period: str = "2024") -> dict:
    """
    Fetch trade data from UN Comtrade.
    reporter: country code (842=USA)
    partner: 0=World
    """
    data = _http_get(f"{COMTRADE_BASE}/C/A/HS", {
        "reporterCode": reporter, "partnerCode": partner,
        "cmdCode": commodity_code, "period": period,
        "flowCode": "M,X",  # imports + exports
    })
    if not data or "data" not in data:
        return {}
    records = data["data"]
    exports = sum(r.get("primaryValue", 0) or 0 for r in records
                  if (r.get("flowDesc") or "").startswith("Export"))
    imports = sum(r.get("primaryValue", 0) or 0 for r in records
                  if (r.get("flowDesc") or "").startswith("Import"))
    return {
        "period": period, "exports_usd": exports, "imports_usd": imports,
        "trade_balance": exports - imports,
        "record_count": len(records),
    }


# ============================================================================
# AGGREGATED CONVENIENCE FUNCTIONS
# ============================================================================

def fetch_full_macro_snapshot() -> dict:
    """Fetch a comprehensive macro snapshot from all available sources."""
    treasury = fetch_treasury_yields()
    time.sleep(0.3)

    fed_funds = fetch_fred_latest("FEDFUNDS")
    gdpnow = fetch_gdpnow()
    nfci = fetch_chicago_fed_nfci()
    cpi = fetch_fred_latest("CPIAUCSL")
    time.sleep(0.3)

    wb_gdp = fetch_world_bank_indicator("NY.GDP.MKTP.KD.ZG", "US")
    imf_rates = fetch_imf_indicators("FM", "FPOLM_PA", ["USA", "GBR", "DEU", "JPN"])
    ecb = fetch_ecb_rates()

    return {
        "treasury_yields": treasury,
        "fed_funds_rate": fed_funds,
        "gdpnow_estimate": gdpnow,
        "nfci": nfci,
        "cpi_index": cpi,
        "world_bank_gdp": wb_gdp[:3] if wb_gdp else [],
        "imf_policy_rates": imf_rates,
        "ecb_rates": ecb,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_full_defi_snapshot() -> dict:
    """Fetch DeFi market overview."""
    protocols = fetch_defillama_protocols(50)
    chains = fetch_defillama_chains()
    stables = fetch_defillama_stablecoins()
    yields = fetch_defillama_yields()

    total_tvl = sum(p.get("tvl", 0) or 0 for p in protocols)
    return {
        "total_defi_tvl": total_tvl,
        "top_protocols": protocols[:20],
        "top_chains": chains[:10],
        "stablecoin_market": stables,
        "top_yields": yields[:20],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_full_sentiment_snapshot(query: str = "RWA tokenization") -> dict:
    """Fetch sentiment from all news/social sources."""
    gdelt_articles = fetch_gdelt_articles(query, max_records=30)
    gdelt_tone = fetch_gdelt_tone(query)
    time.sleep(0.3)

    av_news = fetch_alpha_vantage_news(topics="blockchain,financial_markets")
    newsapi = fetch_newsapi_articles(query)
    bluesky = fetch_bluesky_posts(query, limit=20)
    reddit = fetch_reddit_sentiment("cryptocurrency", query, limit=20)

    return {
        "gdelt_articles": gdelt_articles[:15],
        "gdelt_tone": gdelt_tone,
        "alpha_vantage_news": av_news[:10],
        "newsapi_articles": newsapi[:10],
        "bluesky_posts": bluesky[:10],
        "reddit_posts": reddit[:10],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
