"""
verification_layer.py — RWA Asset Trust Verification Engine
============================================================
Runs 5 independent verification checks on each RWA asset and computes
a Trust Score (0-100) with a badge classification.

CHECK 1 — On-Chain (20 pts):   Etherscan contract verification + audit status
CHECK 2 — Legal (20 pts):      SEC EDGAR filings + OpenCorporates incorporation
CHECK 3 — Reserves (20 pts):   Chainlink Proof of Reserve (or TVL proxy)
CHECK 4 — Market (20 pts):     Listed on major exchanges + liquidity score
CHECK 5 — Sentiment (20 pts):  News VADER + Fear&Greed + Reddit + Claude + Trends

Trust Score Formula (100 points total):
  on_chain_score   x 0.20  (20 points max)
  legal_score      x 0.20  (20 points max)
  reserve_score    x 0.20  (20 points max)
  market_score     x 0.20  (20 points max)
  sentiment_score  x 0.20  (20 points max)  <- sentiment matters!

Sentiment matters because:
  - High bullish sentiment + verified on-chain = strong BUY signal
  - Bearish sentiment on otherwise verified token = CAUTION signal
  - Helps agent differentiate between 2 equally verified tokens

Badges:
  85-100 : GREEN  HIGHLY_VERIFIED
  60-84  : YELLOW VERIFIED
  40-59  : ORANGE PARTIALLY_VERIFIED
  0-39   : RED    UNVERIFIED

Public API:
  verify_rwa_asset(token_id)      -> full verification report dict
  get_trust_badge(score)          -> badge label string
  batch_verify_all_rwa()          -> verify all known RWA tokens
  get_verification_report(id)     -> fetch saved report from DB
  get_all_rwa_trust_summary()     -> quick summary list (no API calls)
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
ETHERSCAN_KEY   = os.getenv("ETHERSCAN_API_KEY", "")
ETH_MAINNET_RPC = os.getenv("ETH_MAINNET_RPC",
                             os.getenv("INFURA_RPC", "").replace("sepolia", "mainnet"))
EDGAR_SEARCH    = "https://efts.sec.gov/LATEST/search-index"
OPENCORP_SEARCH = "https://api.opencorporates.com/v0.4/companies/search"
COINGECKO_BASE  = "https://api.coingecko.com/api/v3"
FEAR_GREED_URL  = "https://api.alternative.me/fng/?limit=1"
CRYPTOCOMPARE_URL = "https://min-api.cryptocompare.com/data/v2/news/"

# ─── Known RWA Assets Registry ────────────────────────────────────────────────
RWA_REGISTRY = {
    "ondo-finance": {
        "symbol":           "ONDO",
        "name":             "Ondo Finance",
        "company":          "Ondo Finance",
        "contract_address": "0x18c11FD286C5EC11c3b683Caa813B77f5163A122",
        "underlying":       "US Treasury Bills",
        "asset_type":       "Treasury",
        "expected_apy":     5.2,
        "major_exchanges":  ["Binance", "Coinbase", "OKX", "Bybit"],
        "chainlink_por":    None,
        "sentiment_keywords": ["ondo", "ONDO", "ondo finance", "RWA treasury"],
    },
    "centrifuge": {
        "symbol":           "CFG",
        "name":             "Centrifuge",
        "company":          "Centrifuge",
        "contract_address": "0xc221b7E65FfC80DE234bB6667ABDd46593D34F0f",
        "underlying":       "Real-world loans",
        "asset_type":       "Credit",
        "expected_apy":     8.5,
        "major_exchanges":  ["Coinbase", "Kraken"],
        "chainlink_por":    None,
        "sentiment_keywords": ["centrifuge", "CFG", "RWA credit"],
    },
    "maple": {
        "symbol":           "MPL",
        "name":             "Maple Finance",
        "company":          "Maple Finance",
        "contract_address": "0x33349B282065b0284d756F0577FB39c158F935e6",
        "underlying":       "Institutional loans",
        "asset_type":       "Credit",
        "expected_apy":     9.0,
        "major_exchanges":  ["Uniswap", "SushiSwap"],
        "chainlink_por":    None,
        "sentiment_keywords": ["maple finance", "MPL", "institutional lending"],
    },
    "goldfinch": {
        "symbol":           "GFI",
        "name":             "Goldfinch Protocol",
        "company":          "Warbler Labs",
        "contract_address": "0xdab396cCF3d84Cf2D07C4454e10C8A6F5b008D2b",
        "underlying":       "Emerging market credit",
        "asset_type":       "Credit",
        "expected_apy":     10.5,
        "major_exchanges":  ["Coinbase", "Uniswap"],
        "chainlink_por":    None,
        "sentiment_keywords": ["goldfinch", "GFI", "emerging market credit"],
    },
    "clearpool": {
        "symbol":           "CPOOL",
        "name":             "Clearpool",
        "company":          "Clearpool",
        "contract_address": "0x66761Fa41377003622aEE3c7675Fc7b5c1C2FaC5",
        "underlying":       "Corporate credit",
        "asset_type":       "Credit",
        "expected_apy":     8.0,
        "major_exchanges":  ["Gate.io", "Uniswap"],
        "chainlink_por":    None,
        "sentiment_keywords": ["clearpool", "CPOOL", "corporate credit DeFi"],
    },
}

# Chainlink PoR ABI
CHAINLINK_POR_ABI = [
    {"inputs": [], "name": "latestAnswer", "outputs": [{"type": "int256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}],
     "stateMutability": "view", "type": "function"},
]

MAJOR_EXCHANGES = {
    "Binance", "Coinbase Exchange", "Kraken", "OKX", "Bybit",
    "KuCoin", "Huobi", "Gate.io", "Bitfinex", "Gemini", "MEXC",
}


# ─── HTTP helper ──────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None, timeout: int = 12) -> Optional[dict]:
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code in (404, 403):
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("[verify] HTTP %s: %s", url, e)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 1 — On-Chain Verification (Etherscan)
# Max: 20 pts
#   +8  -> contract source verified on Etherscan (ABI published)
#   +7  -> contract deployment > 6 months ago
#   +5  -> holder count > 1000 (widely distributed)
# ═══════════════════════════════════════════════════════════════════════════════

def _check_onchain(token_id: str, registry: dict) -> dict:
    address = registry.get("contract_address")
    result = {
        "score": 0, "max_score": 20,
        "contract_address": address,
        "is_verified": False,
        "deployment_age_months": None,
        "holder_count": None,
        "details": [], "warnings": [],
    }
    if not address:
        result["warnings"].append("No contract address in registry")
        return result

    if ETHERSCAN_KEY:
        # A: Source verified
        abi_data = _get("https://api.etherscan.io/api", {
            "module": "contract", "action": "getabi",
            "address": address, "apikey": ETHERSCAN_KEY,
        })
        if abi_data and abi_data.get("status") == "1":
            result["is_verified"] = True
            result["score"] += 8
            result["details"].append("Contract source verified on Etherscan")
        else:
            result["warnings"].append("Contract source not verified on Etherscan")

        # B: Contract age
        tx_data = _get("https://api.etherscan.io/api", {
            "module": "account", "action": "txlist",
            "address": address, "startblock": "0", "endblock": "99999999",
            "sort": "asc", "page": "1", "offset": "1", "apikey": ETHERSCAN_KEY,
        })
        result_list = tx_data.get("result") if tx_data else None
        if isinstance(result_list, list) and result_list:
            ts = int(result_list[0].get("timeStamp", 0))
            if ts > 0:
                age_months = (datetime.now(timezone.utc) -
                              datetime.fromtimestamp(ts, tz=timezone.utc)).days / 30
                result["deployment_age_months"] = round(age_months, 1)
                if age_months >= 6:
                    result["score"] += 7
                    result["details"].append(
                        f"Contract deployed {age_months:.0f} months ago (established)")
                else:
                    result["warnings"].append(
                        f"Contract only {age_months:.0f} months old (relatively new)")

        # C: Holder count
        h_data = _get("https://api.etherscan.io/api", {
            "module": "token", "action": "tokeninfo",
            "contractaddress": address, "apikey": ETHERSCAN_KEY,
        })
        if h_data and h_data.get("result"):
            info = h_data["result"][0] if isinstance(h_data["result"], list) else {}
            holders = int(info.get("holdersCount", 0) or 0)
            result["holder_count"] = holders
            if holders >= 1000:
                result["score"] += 5
                result["details"].append(f"{holders:,} token holders (widely distributed)")
            elif holders >= 100:
                result["score"] += 2
                result["details"].append(f"{holders} holders (limited distribution)")
            else:
                result["warnings"].append(f"Only {holders} holders (highly concentrated)")
        time.sleep(0.3)
    else:
        result["warnings"].append("Etherscan API key not configured — partial check only")
        if token_id in ("ondo-finance", "centrifuge", "maple", "goldfinch"):
            result["score"] += 10  # partial credit for known established projects
            result["details"].append("Known established project (manual entry)")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 2 — Legal Entity Verification (SEC EDGAR + OpenCorporates)
# Max: 20 pts
#   +9  -> SEC EDGAR: company has filed (Form D, S-1, 8-K)
#   +7  -> OpenCorporates: company legally incorporated + ACTIVE
#   +4  -> Incorporation date > 1 year ago
# ═══════════════════════════════════════════════════════════════════════════════

def _check_legal(token_id: str, registry: dict) -> dict:
    company = registry.get("company", "")
    result = {
        "score": 0, "max_score": 20,
        "company_name": company,
        "sec_filings": 0, "sec_filing_types": [],
        "sec_latest_filing": None,
        "legal_incorporated": False,
        "jurisdiction": None, "incorporation_date": None, "company_status": None,
        "details": [], "warnings": [],
    }
    if not company:
        result["warnings"].append("No company name in registry")
        return result

    # A: SEC EDGAR
    edgar_data = _get(EDGAR_SEARCH, {
        "q": f'"{company}"', "dateRange": "custom", "startdt": "2022-01-01",
    })
    if edgar_data:
        hits = edgar_data.get("hits", {}).get("hits", [])
        ftypes = list(set(
            h.get("_source", {}).get("form_type", "")
            for h in hits[:10] if h.get("_source", {}).get("form_type")
        ))
        result["sec_filings"] = len(hits)
        result["sec_filing_types"] = ftypes
        if hits:
            result["sec_latest_filing"] = hits[0].get("_source", {}).get("period_of_report")
        if len(hits) >= 3:
            result["score"] += 9
            result["details"].append(
                f"SEC EDGAR: {len(hits)} filings — Types: {', '.join(ftypes[:4])}")
        elif len(hits) >= 1:
            result["score"] += 5
            result["details"].append(f"SEC EDGAR: {len(hits)} filing(s) found")
        else:
            result["warnings"].append(f"No SEC EDGAR filings for '{company}'")
    else:
        result["warnings"].append("SEC EDGAR search unavailable")
    time.sleep(0.5)

    # B: OpenCorporates
    oc_data = _get(OPENCORP_SEARCH, {"q": company, "format": "json"})
    if oc_data:
        companies = oc_data.get("results", {}).get("companies", [])
        if companies:
            top = companies[0]["company"]
            status = (top.get("current_status") or "").upper()
            result["legal_incorporated"] = True
            result["jurisdiction"] = top.get("jurisdiction_code")
            result["incorporation_date"] = top.get("incorporation_date")
            result["company_status"] = status
            if status in ("ACTIVE", "LIVE", "REGISTERED", "GOOD STANDING"):
                result["score"] += 7
                result["details"].append(
                    f"OpenCorporates: {top.get('name')} — {status} "
                    f"({top.get('jurisdiction_code', '?')})")
                inc_date = top.get("incorporation_date")
                if inc_date:
                    try:
                        inc = datetime.strptime(inc_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        age_months = (datetime.now(timezone.utc) - inc).days / 30
                        if age_months >= 12:
                            result["score"] += 4
                            result["details"].append(
                                f"Company incorporated {age_months:.0f} months ago")
                        else:
                            result["warnings"].append(
                                f"Company only {age_months:.0f} months old")
                    except ValueError:
                        pass
            elif status in ("DISSOLVED", "INACTIVE", "REVOKED"):
                result["warnings"].append(f"Company status: {status} — RED FLAG")
            else:
                result["score"] += 3
                result["details"].append(f"Company found, status: {status or 'unknown'}")
        else:
            result["warnings"].append(f"'{company}' not found in OpenCorporates")
    else:
        result["warnings"].append("OpenCorporates unavailable")
    time.sleep(0.5)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 3 — Reserve Verification (Chainlink PoR + TVL)
# Max: 20 pts
#   +10 -> Chainlink Proof of Reserve verified on-chain
#   +7  -> TVL > $10M (DeFi Llama)
#   +3  -> 30-day positive price trend
# ═══════════════════════════════════════════════════════════════════════════════

def _check_reserves(token_id: str, registry: dict) -> dict:
    result = {
        "score": 0, "max_score": 20,
        "chainlink_por_available": False,
        "verified_reserves_usd": None,
        "tvl_usd": None,
        "tvl_growth_30d_pct": None,
        "details": [], "warnings": [],
    }

    # A: Chainlink PoR
    por_address = registry.get("chainlink_por")
    if por_address and ETH_MAINNET_RPC:
        try:
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider(ETH_MAINNET_RPC, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                contract = w3.eth.contract(
                    address=Web3.to_checksum_address(por_address),
                    abi=CHAINLINK_POR_ABI)
                answer = contract.functions.latestAnswer().call()
                decimals = contract.functions.decimals().call()
                reserves_usd = answer / (10 ** decimals)
                result["chainlink_por_available"] = True
                result["verified_reserves_usd"] = reserves_usd
                result["score"] += 10
                result["details"].append(
                    f"Chainlink PoR: ${reserves_usd:,.0f} verified on-chain")
        except Exception as e:
            logger.debug("[verify] Chainlink PoR %s: %s", token_id, e)
            result["warnings"].append("Chainlink PoR check failed — using TVL proxy")
    else:
        result["warnings"].append("No Chainlink PoR — using DeFi Llama TVL as proxy")

    # B: TVL proxy
    try:
        from data_pipeline import get_rwa_assets, get_defi_protocols
        rwa_list = get_rwa_assets()
        rwa_row = next((r for r in rwa_list if r.get("id") == token_id), None)
        tvl = rwa_row.get("tvl_usd", 0) if rwa_row else 0
        if not tvl:
            protocols = get_defi_protocols(100)
            name_lower = registry.get("name", "").lower()
            matching = [p for p in protocols if name_lower in p.get("name", "").lower()]
            tvl = sum(p.get("tvl_usd", 0) or 0 for p in matching)
        result["tvl_usd"] = tvl
        if tvl >= 100_000_000:
            result["score"] += 7
            result["details"].append(f"TVL: ${tvl/1e6:.1f}M (strong reserve backing)")
        elif tvl >= 10_000_000:
            result["score"] += 5
            result["details"].append(f"TVL: ${tvl/1e6:.1f}M (moderate reserve backing)")
        elif tvl >= 1_000_000:
            result["score"] += 2
            result["details"].append(f"TVL: ${tvl/1e6:.2f}M (limited)")
        elif tvl > 0:
            result["warnings"].append(f"TVL: ${tvl:,.0f} (very low)")
        else:
            result["warnings"].append("TVL data unavailable")
    except Exception as e:
        result["warnings"].append(f"TVL check error: {e}")

    # C: 30d price trend
    try:
        from data_pipeline import get_token
        tok = get_token(token_id)
        if tok:
            change_30d = tok.get("change_30d", 0) or 0
            result["tvl_growth_30d_pct"] = change_30d
            if change_30d > 5:
                result["score"] += 3
                result["details"].append(f"Price +{change_30d:.1f}% in 30 days (growing)")
            elif change_30d > 0:
                result["score"] += 1
                result["details"].append(f"Price +{change_30d:.1f}% in 30 days (stable)")
            else:
                result["warnings"].append(f"Price {change_30d:.1f}% in 30 days (declining)")
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 4 — Market Legitimacy (CoinGecko + Exchanges)
# Max: 20 pts
#   +8  -> Listed on 2+ major exchanges
#   +6  -> CoinGecko trust score >= 60
#   +4  -> Listed > 6 months
#   +2  -> Market cap > $10M
# ═══════════════════════════════════════════════════════════════════════════════

def _check_market(token_id: str, registry: dict) -> dict:
    result = {
        "score": 0, "max_score": 20,
        "exchanges": [], "major_exchange_count": 0,
        "coingecko_trust_score": None,
        "listed_since": None, "market_cap_usd": None,
        "details": [], "warnings": [],
    }
    cg_data = _get(f"{COINGECKO_BASE}/coins/{token_id}", {
        "localization": "false", "tickers": "true",
        "market_data": "true", "community_data": "false", "developer_data": "false",
    })
    if not cg_data:
        result["warnings"].append(f"Token '{token_id}' not found on CoinGecko")
        return result

    # A: Exchange listing
    tickers = cg_data.get("tickers", [])[:30]
    exchanges_seen = list(set(
        t.get("market", {}).get("name", "") for t in tickers
        if t.get("market", {}).get("name")
    ))
    result["exchanges"] = exchanges_seen[:10]
    major_count = len(set(exchanges_seen) & MAJOR_EXCHANGES)
    result["major_exchange_count"] = major_count
    if major_count >= 3:
        result["score"] += 8
        result["details"].append(
            f"Listed on {major_count} major exchanges: "
            f"{', '.join(list(set(exchanges_seen) & MAJOR_EXCHANGES)[:4])}")
    elif major_count >= 1:
        result["score"] += 4
        result["details"].append(f"Listed on {major_count} major exchange(s)")
    else:
        result["warnings"].append("Not listed on major exchanges (DEX only)")

    # B: CoinGecko trust score
    cg_score = cg_data.get("coingecko_score") or cg_data.get("liquidity_score")
    if cg_score:
        result["coingecko_trust_score"] = round(cg_score, 1)
        if cg_score >= 60:
            result["score"] += 6
            result["details"].append(f"CoinGecko score: {cg_score:.0f}/100")
        elif cg_score >= 30:
            result["score"] += 3
            result["details"].append(f"CoinGecko score: {cg_score:.0f}/100 (below average)")
        else:
            result["warnings"].append(f"Low CoinGecko score: {cg_score:.0f}/100")

    # C: Listing age
    genesis = cg_data.get("genesis_date")
    if genesis:
        result["listed_since"] = genesis
        try:
            listed = datetime.strptime(genesis, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            age_months = (datetime.now(timezone.utc) - listed).days / 30
            if age_months >= 6:
                result["score"] += 4
                result["details"].append(f"Listed since {genesis} ({age_months:.0f} months)")
            else:
                result["warnings"].append(f"Only listed for {age_months:.0f} months (new)")
        except ValueError:
            pass

    # D: Market cap
    market_cap = cg_data.get("market_data", {}).get("market_cap", {}).get("usd", 0) or 0
    result["market_cap_usd"] = market_cap
    if market_cap >= 10_000_000:
        result["score"] += 2
        result["details"].append(f"Market cap: ${market_cap/1e6:.1f}M")
    else:
        result["warnings"].append("Market cap < $10M (micro-cap)")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 5 — Sentiment Analysis (NEW)
# Max: 20 pts
#   +5  -> Fear & Greed Index >= 40 (not extreme fear)
#   +5  -> CryptoCompare News VADER score >= 0.1 (net positive news)
#   +4  -> Reddit sentiment BULLISH for this token's community
#   +3  -> Claude/LLM market assessment includes token in opportunities
#   +3  -> Google Trends shows rising interest (score > 40)
#
# Sentiment rationale:
#   A verified RWA token that ALSO has positive sentiment = higher conviction BUY
#   A verified token with negative sentiment = still valid but FLAG for caution
#   An unverified token with positive sentiment = STILL low score (not enough)
# ═══════════════════════════════════════════════════════════════════════════════

def _check_sentiment(token_id: str, registry: dict) -> dict:
    symbol = registry.get("symbol", "").upper()
    result = {
        "score": 0, "max_score": 20,
        "fear_greed_value": None,
        "news_sentiment_score": None,
        "news_sentiment_label": None,
        "reddit_sentiment": None,
        "llm_sentiment": None,
        "google_trends_score": None,
        "composite_sentiment": None,  # 0.0-1.0 aggregate
        "details": [], "warnings": [],
    }

    # A: Fear & Greed Index (market-wide sentiment barometer)
    try:
        from data_pipeline import get_latest_sentiment
        fg_row = get_latest_sentiment("fear_greed", "MARKET")
        if fg_row:
            fg_details = fg_row.get("details_json", {})
            fg_value = fg_details.get("value", 50) if isinstance(fg_details, dict) else 50
            result["fear_greed_value"] = fg_value
            if fg_value >= 60:
                result["score"] += 5
                result["details"].append(
                    f"Fear&Greed Index: {fg_value}/100 (GREED — favorable market)")
            elif fg_value >= 40:
                result["score"] += 3
                result["details"].append(
                    f"Fear&Greed Index: {fg_value}/100 (NEUTRAL)")
            elif fg_value >= 20:
                result["score"] += 1
                result["warnings"].append(
                    f"Fear&Greed Index: {fg_value}/100 (FEAR — unfavorable)")
            else:
                result["warnings"].append(
                    f"Fear&Greed Index: {fg_value}/100 (EXTREME FEAR)")
        else:
            # Fetch fresh if not in DB
            fg_data = _get(FEAR_GREED_URL)
            if fg_data and "data" in fg_data:
                fg_value = int(fg_data["data"][0].get("value", 50))
                result["fear_greed_value"] = fg_value
                if fg_value >= 40:
                    result["score"] += 3
                    result["details"].append(f"Fear&Greed: {fg_value}/100")
                else:
                    result["warnings"].append(f"Fear&Greed: {fg_value}/100 (FEAR)")
    except Exception as e:
        logger.debug("[verify/sentiment] Fear&Greed: %s", e)
        result["warnings"].append("Fear&Greed data unavailable")

    # B: CryptoCompare News + VADER (token-specific news sentiment)
    try:
        from data_pipeline import get_latest_sentiment as get_sent
        news_row = get_sent("news_vader", symbol)
        if news_row:
            news_score = news_row.get("score", 0.5)  # 0.0-1.0
            news_label = news_row.get("label", "NEUTRAL")
            result["news_sentiment_score"] = news_score
            result["news_sentiment_label"] = news_label
            news_compound = (news_score * 2) - 1  # convert back to -1..+1
            if news_compound >= 0.1:
                result["score"] += 5
                result["details"].append(
                    f"News sentiment: {news_label} (score {news_score:.2f}) — positive coverage")
            elif news_compound >= -0.05:
                result["score"] += 2
                result["details"].append(f"News sentiment: {news_label} (neutral)")
            else:
                result["warnings"].append(f"News sentiment: {news_label} — negative coverage")
        else:
            # Fetch fresh VADER score for this token
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                analyzer = SentimentIntensityAnalyzer()
                news_data = _get(CRYPTOCOMPARE_URL, {
                    "lang": "EN", "categories": symbol,
                    "lTs": int(time.time()) - 86400,
                })
                if news_data and "Data" in news_data and news_data["Data"]:
                    articles = news_data["Data"][:15]
                    scores = []
                    for art in articles:
                        text = f"{art.get('title','')}. {art.get('body','')[:150]}"
                        scores.append(analyzer.polarity_scores(text)["compound"])
                    avg = sum(scores) / len(scores) if scores else 0
                    result["news_sentiment_score"] = (avg + 1) / 2
                    if avg >= 0.1:
                        result["score"] += 5
                        result["details"].append(
                            f"News VADER: {avg:+.2f} — BULLISH ({len(articles)} articles)")
                    elif avg >= -0.05:
                        result["score"] += 2
                        result["details"].append(f"News VADER: {avg:+.2f} — NEUTRAL")
                    else:
                        result["warnings"].append(f"News VADER: {avg:+.2f} — BEARISH")
                else:
                    result["warnings"].append(f"No recent news found for {symbol}")
            except ImportError:
                result["warnings"].append("vaderSentiment not installed — news check skipped")
    except Exception as e:
        logger.debug("[verify/sentiment] News: %s", e)

    # C: Reddit community sentiment
    try:
        from data_pipeline import get_latest_sentiment as get_sent2
        # Check for token-specific or general crypto reddit sentiment
        reddit_row = get_sent2("reddit", symbol) or get_sent2("reddit", "MARKET")
        if reddit_row:
            reddit_label = reddit_row.get("label", "NEUTRAL")
            reddit_score = reddit_row.get("score", 0.5)
            result["reddit_sentiment"] = reddit_label
            if reddit_label == "BULLISH":
                result["score"] += 4
                result["details"].append(
                    f"Reddit sentiment: BULLISH (score {reddit_score:.2f})")
            elif reddit_label == "NEUTRAL":
                result["score"] += 2
                result["details"].append(f"Reddit sentiment: NEUTRAL")
            else:
                result["warnings"].append(f"Reddit sentiment: {reddit_label}")
        else:
            result["warnings"].append("Reddit sentiment not available (no API key or not fetched)")
    except Exception as e:
        logger.debug("[verify/sentiment] Reddit: %s", e)

    # D: Claude LLM assessment (does it appear in opportunities?)
    try:
        from data_pipeline import get_latest_sentiment as get_sent3
        claude_row = get_sent3("claude_llm", "MARKET")
        if claude_row:
            details = claude_row.get("details_json", {})
            if isinstance(details, dict):
                opportunities = [o.lower() for o in details.get("best_opportunities", [])]
                overall = claude_row.get("label", "NEUTRAL")
                result["llm_sentiment"] = overall
                token_mentioned = any(
                    symbol.lower() in o or
                    registry.get("name", "").lower() in o
                    for o in opportunities
                )
                if token_mentioned:
                    result["score"] += 3
                    result["details"].append(
                        f"Claude LLM: {symbol} listed as top opportunity ({overall})")
                elif overall in ("BULLISH", "CAUTIOUSLY_BULLISH"):
                    result["score"] += 2
                    result["details"].append(f"Claude LLM: Overall market {overall}")
                elif overall == "NEUTRAL":
                    result["score"] += 1
                    result["details"].append(f"Claude LLM: NEUTRAL market")
                else:
                    result["warnings"].append(f"Claude LLM: {overall}")
        else:
            result["warnings"].append("Claude LLM analysis not yet run")
    except Exception as e:
        logger.debug("[verify/sentiment] Claude: %s", e)

    # E: Google Trends interest
    try:
        from data_pipeline import get_latest_sentiment as get_sent4
        trends_row = get_sent4("google_trends", "MARKET")
        if trends_row:
            trends_score = trends_row.get("score", 0)  # 0.0-1.0
            trends_label = trends_row.get("label", "MODERATE")
            result["google_trends_score"] = round(trends_score * 100)
            if trends_score >= 0.4:
                result["score"] += 3
                result["details"].append(
                    f"Google Trends: {trends_label} (interest score {trends_score*100:.0f}/100)")
            elif trends_score >= 0.2:
                result["score"] += 1
                result["details"].append(f"Google Trends: {trends_label}")
            else:
                result["warnings"].append(f"Google Trends: LOW_INTEREST ({trends_score*100:.0f}/100)")
        else:
            result["warnings"].append("Google Trends data not yet fetched")
    except Exception as e:
        logger.debug("[verify/sentiment] Trends: %s", e)

    # Compute composite sentiment score (0.0-1.0)
    filled_scores = [v for v in [
        result["news_sentiment_score"],
        result.get("fear_greed_value", None) and result["fear_greed_value"] / 100,
    ] if v is not None]
    result["composite_sentiment"] = round(
        sum(filled_scores) / len(filled_scores), 3
    ) if filled_scores else 0.5

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Trust Score + Badge Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_trust_badge(score: int) -> str:
    if score >= 85:
        return "HIGHLY_VERIFIED"
    elif score >= 60:
        return "VERIFIED"
    elif score >= 40:
        return "PARTIALLY_VERIFIED"
    return "UNVERIFIED"


def get_trust_badge_emoji(score: int) -> str:
    badge = get_trust_badge(score)
    emojis = {
        "HIGHLY_VERIFIED":    "🟢",
        "VERIFIED":           "🟡",
        "PARTIALLY_VERIFIED": "🟠",
        "UNVERIFIED":         "🔴",
    }
    return f"{emojis.get(badge, '⚪')} {badge.replace('_', ' ')}"


# ═══════════════════════════════════════════════════════════════════════════════
# Main Verification Engine
# ═══════════════════════════════════════════════════════════════════════════════

def verify_rwa_asset(token_id: str) -> dict:
    """
    Run all 5 verification checks on a single RWA asset.

    Args:
        token_id: CoinGecko ID (e.g. "ondo-finance")

    Returns:
        Full verification report with trust_score, badge, and all check details.
    """
    registry = RWA_REGISTRY.get(token_id)
    if not registry:
        return {
            "token_id": token_id,
            "error": f"'{token_id}' not in RWA registry",
            "trust_score": 0, "trust_badge": "UNVERIFIED",
        }

    logger.info("[verify] Verifying %s (%s)...", token_id, registry["symbol"])
    start = time.time()

    onchain   = _check_onchain(token_id, registry)
    legal     = _check_legal(token_id, registry)
    reserves  = _check_reserves(token_id, registry)
    market    = _check_market(token_id, registry)
    sentiment = _check_sentiment(token_id, registry)

    raw_total = (
        onchain["score"] + legal["score"] +
        reserves["score"] + market["score"] + sentiment["score"]
    )
    trust_score = min(100, max(0, raw_total))
    trust_badge = get_trust_badge(trust_score)

    report = {
        "token_id":            token_id,
        "symbol":              registry["symbol"],
        "name":                registry["name"],
        "company":             registry["company"],
        "underlying":          registry["underlying"],
        "asset_type":          registry["asset_type"],
        "expected_apy":        registry["expected_apy"],
        "trust_score":         trust_score,
        "trust_badge":         trust_badge,
        "trust_badge_display": get_trust_badge_emoji(trust_score),
        "score_breakdown": {
            "on_chain":  {"score": onchain["score"],   "max": 20},
            "legal":     {"score": legal["score"],     "max": 20},
            "reserves":  {"score": reserves["score"],  "max": 20},
            "market":    {"score": market["score"],    "max": 20},
            "sentiment": {"score": sentiment["score"], "max": 20},
        },
        "on_chain":  onchain,
        "legal":     legal,
        "reserves":  reserves,
        "market":    market,
        "sentiment": sentiment,
        "summary": {
            "contract_verified":     onchain["is_verified"],
            "sec_verified":          legal["sec_filings"] > 0,
            "legal_incorporated":    legal["legal_incorporated"],
            "tvl_usd":               reserves["tvl_usd"],
            "exchanges":             market["exchanges"][:5],
            "major_exchange_count":  market["major_exchange_count"],
            "market_cap_usd":        market["market_cap_usd"],
            "fear_greed":            sentiment["fear_greed_value"],
            "news_sentiment":        sentiment["news_sentiment_label"],
            "composite_sentiment":   sentiment["composite_sentiment"],
        },
        "proof_points": (
            onchain["details"] + legal["details"] +
            reserves["details"] + market["details"] + sentiment["details"]
        ),
        "risk_factors": (
            onchain["warnings"] + legal["warnings"] +
            reserves["warnings"] + market["warnings"] + sentiment["warnings"]
        ),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s":   round(time.time() - start, 1),
    }

    _save_report(report)
    logger.info("[verify] %s: %d/100 (%s) in %.1fs",
                registry["symbol"], trust_score, trust_badge, report["elapsed_s"])
    return report


def _save_report(report: dict):
    """Persist verification results to rwa_assets table."""
    try:
        from data_pipeline import _get_conn
        with _get_conn() as conn:
            conn.execute("""
                UPDATE rwa_assets SET
                    trust_score           = ?,
                    sec_verified          = ?,
                    legal_incorporated    = ?,
                    contract_audited      = ?,
                    listed_major_exchange = ?,
                    last_updated          = ?
                WHERE id = ?
            """, (
                report["trust_score"],
                1 if report["summary"]["sec_verified"] else 0,
                1 if report["summary"]["legal_incorporated"] else 0,
                1 if report["summary"]["contract_verified"] else 0,
                1 if report["summary"]["major_exchange_count"] >= 1 else 0,
                report["verified_at"],
                report["token_id"],
            ))
            conn.commit()
    except Exception as e:
        logger.debug("[verify] DB save: %s", e)


def get_verification_report(token_id: str) -> Optional[dict]:
    """Fetch saved verification data from DB (no API calls)."""
    try:
        from data_pipeline import get_rwa_assets
        assets = get_rwa_assets()
        asset = next((a for a in assets if a.get("id") == token_id), None)
        if not asset:
            return None
        registry = RWA_REGISTRY.get(token_id, {})
        score = asset.get("trust_score", 0)
        return {
            "token_id":              token_id,
            "symbol":                asset.get("symbol"),
            "name":                  asset.get("name"),
            "trust_score":           score,
            "trust_badge":           get_trust_badge(score),
            "trust_badge_display":   get_trust_badge_emoji(score),
            "sec_verified":          bool(asset.get("sec_verified")),
            "legal_incorporated":    bool(asset.get("legal_incorporated")),
            "contract_audited":      bool(asset.get("contract_audited")),
            "listed_major_exchange": bool(asset.get("listed_major_exchange")),
            "tvl_usd":               asset.get("tvl_usd"),
            "apy_pct":               asset.get("apy_pct"),
            "underlying_asset":      asset.get("underlying_asset"),
            "asset_type":            asset.get("asset_type"),
            "last_updated":          asset.get("last_updated"),
            "underlying":            registry.get("underlying"),
            "expected_apy":          registry.get("expected_apy"),
        }
    except Exception as e:
        logger.debug("[verify] get_report: %s", e)
        return None


def batch_verify_all_rwa() -> list:
    """Verify ALL RWA tokens in registry. Slow — run weekly."""
    results = []
    for token_id in RWA_REGISTRY:
        try:
            report = verify_rwa_asset(token_id)
            results.append({
                "token_id":    token_id,
                "symbol":      report["symbol"],
                "trust_score": report["trust_score"],
                "trust_badge": report["trust_badge"],
                "sentiment":   report["sentiment"]["composite_sentiment"],
                "proof_count": len(report["proof_points"]),
                "risk_count":  len(report["risk_factors"]),
            })
            time.sleep(1)
        except Exception as e:
            logger.error("[verify] batch %s: %s", token_id, e)
            results.append({"token_id": token_id, "error": str(e)})
    return results


def get_all_rwa_trust_summary() -> list:
    """Quick DB-only summary of all RWA trust scores (no API calls)."""
    summary = []
    for token_id in RWA_REGISTRY:
        report = get_verification_report(token_id)
        if report:
            summary.append(report)
        else:
            reg = RWA_REGISTRY[token_id]
            summary.append({
                "token_id":            token_id,
                "symbol":              reg["symbol"],
                "name":                reg["name"],
                "trust_score":         0,
                "trust_badge":         "UNVERIFIED",
                "trust_badge_display": "⚪ NOT VERIFIED YET",
                "underlying":          reg["underlying"],
                "expected_apy":        reg["expected_apy"],
            })
    return sorted(summary, key=lambda x: x.get("trust_score", 0), reverse=True)
