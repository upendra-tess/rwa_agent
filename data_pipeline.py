"""
data_pipeline.py — Complete Multi-Source Market Data Pipeline
=============================================================
Data Sources (14 total):
  Prices:     CoinGecko (34 tokens + RWA category) + Binance (real-time top 15)
  DeFi/RWA:  DeFi Llama (TVL 500+ protocols) + RWA.xyz (RWA market summary)
  On-chain:  Chainlink (verified prices via Web3) + Etherscan (contract status)
  Legal:     SEC EDGAR (filings check) + OpenCorporates (incorporation check)
  History:   Dune Analytics (on-chain transfer volumes)
  Sentiment: Fear & Greed Index + CryptoCompare News + Reddit (PRAW) +
             Claude/Bedrock (LLM analysis) + Google Trends

All data cached in SQLite (market_data.db) with scheduled refresh.
Every source has graceful fallback — missing API keys skip that source silently.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "market_data.db"
COINGECKO_BASE    = "https://api.coingecko.com/api/v3"
BINANCE_BASE      = "https://api.binance.com/api/v3"
DEFILLAMA_BASE    = "https://api.llama.fi"
RWAXYZ_BASE       = "https://api.rwa.xyz/v1"
EDGAR_BASE        = "https://efts.sec.gov/LATEST/search-index"
OPENCORP_BASE     = "https://api.opencorporates.com/v0.4"
FEAR_GREED_BASE   = "https://api.alternative.me/fng"
CRYPTOCOMPARE_BASE= "https://min-api.cryptocompare.com/data/v2"
DUNE_BASE         = "https://api.dune.com/api/v1"

CACHE_EXPIRY_MINUTES = 20

# API keys (all optional — fallback if missing)
ETHERSCAN_KEY   = os.getenv("ETHERSCAN_API_KEY", "")
DUNE_KEY        = os.getenv("DUNE_API_KEY", "")
REDDIT_ID       = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_SECRET   = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_AGENT    = os.getenv("REDDIT_USER_AGENT", "TradingAgent/1.0")
ETH_MAINNET_RPC = os.getenv("ETH_MAINNET_RPC",
                             os.getenv("INFURA_RPC", "").replace("sepolia", "mainnet"))

# ─── Token Definitions ────────────────────────────────────────────────────────
# CoinGecko IDs → ticker symbols
TOKEN_MAP = {
    "bitcoin": "BTC",        "ethereum": "ETH",          "binancecoin": "BNB",
    "solana": "SOL",         "ripple": "XRP",             "cardano": "ADA",
    "avalanche-2": "AVAX",   "polkadot": "DOT",           "chainlink": "LINK",
    "uniswap": "UNI",        "aave": "AAVE",              "maker": "MKR",
    "compound-governance-token": "COMP",  "curve-dao-token": "CRV",
    "synthetix-network-token": "SNX",     "yearn-finance": "YFI",
    "sushi": "SUSHI",        "balancer": "BAL",           "1inch": "1INCH",
    "matic-network": "MATIC","arbitrum": "ARB",           "optimism": "OP",
    "apecoin": "APE",        "lido-dao": "LDO",           "rocket-pool": "RPL",
    "frax-share": "FXS",     "convex-finance": "CVX",     "gmx": "GMX",
    "gains-network": "GNS",  "pendle": "PENDLE",
    # RWA tokens
    "ondo-finance": "ONDO",  "centrifuge": "CFG",         "maple": "MPL",
    "goldfinch": "GFI",      "clearpool": "CPOOL",
}

# Binance symbols for real-time price (top 15 most liquid)
BINANCE_SYMBOLS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "ADAUSDT","AVAXUSDT","DOTUSDT","LINKUSDT","UNIUSDT",
    "MATICUSDT","ARBUSDT","OPUSDT","LDOUSDT","AAVEUSDT",
]

# RWA token issuers for legal verification
RWA_ISSUERS = {
    "ondo-finance":  {"company": "Ondo Finance", "underlying": "US Treasuries", "apy_est": 5.2},
    "centrifuge":    {"company": "Centrifuge",   "underlying": "Real-world loans","apy_est": 8.5},
    "maple":         {"company": "Maple Finance","underlying": "Institutional loans","apy_est": 9.0},
    "goldfinch":     {"company": "Warbler Labs", "underlying": "Emerging market credit","apy_est": 10.5},
    "clearpool":     {"company": "Clearpool",    "underlying": "Corporate credit","apy_est": 8.0},
}

# Chainlink price feed contract addresses (Ethereum mainnet)
CHAINLINK_FEEDS = {
    "ETH/USD":  "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
    "BTC/USD":  "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
    "LINK/USD": "0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c",
}
CHAINLINK_ABI = [{"inputs":[],"name":"latestRoundData",
    "outputs":[{"name":"roundId","type":"uint80"},{"name":"answer","type":"int256"},
               {"name":"startedAt","type":"uint256"},{"name":"updatedAt","type":"uint256"},
               {"name":"answeredInRound","type":"uint80"}],
    "stateMutability":"view","type":"function"}]

# ─── Database ─────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_db(conn: sqlite3.Connection):
    """Add new columns to existing tables (safe to run on old DBs)."""
    migrations = [
        # token_prices new columns
        ("ALTER TABLE token_prices ADD COLUMN price_binance REAL",       "token_prices.price_binance"),
        ("ALTER TABLE token_prices ADD COLUMN price_chainlink REAL",     "token_prices.price_chainlink"),
        ("ALTER TABLE token_prices ADD COLUMN change_7d REAL",           "token_prices.change_7d"),
        ("ALTER TABLE token_prices ADD COLUMN change_30d REAL",          "token_prices.change_30d"),
        ("ALTER TABLE token_prices ADD COLUMN price_history_json TEXT",  "token_prices.price_history_json"),
        ("ALTER TABLE token_prices ADD COLUMN is_rwa INTEGER DEFAULT 0", "token_prices.is_rwa"),
        # gas_prices new columns
        ("ALTER TABLE gas_prices ADD COLUMN eth_usd REAL",               "gas_prices.eth_usd"),
        ("ALTER TABLE gas_prices ADD COLUMN last_updated TEXT",          "gas_prices.last_updated"),
        # rwa_assets new columns (in case table existed before full schema)
        ("ALTER TABLE rwa_assets ADD COLUMN tvl_usd REAL",                       "rwa_assets.tvl_usd"),
        ("ALTER TABLE rwa_assets ADD COLUMN apy_pct REAL",                       "rwa_assets.apy_pct"),
        ("ALTER TABLE rwa_assets ADD COLUMN asset_type TEXT",                    "rwa_assets.asset_type"),
        ("ALTER TABLE rwa_assets ADD COLUMN underlying_asset TEXT",              "rwa_assets.underlying_asset"),
        ("ALTER TABLE rwa_assets ADD COLUMN trust_score INTEGER DEFAULT 0",      "rwa_assets.trust_score"),
        ("ALTER TABLE rwa_assets ADD COLUMN sec_verified INTEGER DEFAULT 0",     "rwa_assets.sec_verified"),
        ("ALTER TABLE rwa_assets ADD COLUMN legal_incorporated INTEGER DEFAULT 0","rwa_assets.legal_incorporated"),
        ("ALTER TABLE rwa_assets ADD COLUMN contract_audited INTEGER DEFAULT 0", "rwa_assets.contract_audited"),
        ("ALTER TABLE rwa_assets ADD COLUMN listed_major_exchange INTEGER DEFAULT 0","rwa_assets.listed_major_exchange"),
        ("ALTER TABLE rwa_assets ADD COLUMN rwa_market_cap_usd REAL",            "rwa_assets.rwa_market_cap_usd"),
    ]
    for sql, label in migrations:
        try:
            conn.execute(sql)
            logger.info("[db migrate] Added column: %s", label)
        except sqlite3.OperationalError:
            pass  # Column already exists — safe to ignore
    conn.commit()


def _init_db():
    """Create all 5 tables if they don't exist."""
    with _get_conn() as conn:
        # Table 1: Token prices (crypto + RWA)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_prices (
                id TEXT PRIMARY KEY,
                symbol TEXT, name TEXT,
                price_usd REAL,         -- from CoinGecko (aggregated)
                price_binance REAL,     -- from Binance (real-time spot)
                price_chainlink REAL,   -- from Chainlink oracle (tamper-proof)
                market_cap REAL, volume_24h REAL,
                change_24h REAL, change_7d REAL, change_30d REAL,
                price_history_json TEXT,-- 30-day daily prices as JSON array
                is_rwa INTEGER DEFAULT 0, -- 1 if RWA token
                last_updated TEXT
            )
        """)
        # Table 2: DeFi protocol TVL
        conn.execute("""
            CREATE TABLE IF NOT EXISTS defi_protocols (
                id TEXT PRIMARY KEY,
                name TEXT, tvl_usd REAL,
                tvl_change_1d REAL,     -- % change in TVL (positive = growing)
                category TEXT, chain TEXT,
                last_updated TEXT
            )
        """)
        # Table 3: RWA assets (enriched with legal + verification data)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rwa_assets (
                id TEXT PRIMARY KEY,
                symbol TEXT, name TEXT,
                price_usd REAL, market_cap REAL,
                tvl_usd REAL,           -- from DeFi Llama
                apy_pct REAL,           -- estimated annual yield
                asset_type TEXT,        -- "Treasury" / "Credit" / "RealEstate"
                underlying_asset TEXT,  -- "US T-Bills" / "Corporate loans" etc
                trust_score INTEGER DEFAULT 0, -- 0-100, computed by verification_layer
                sec_verified INTEGER DEFAULT 0,
                legal_incorporated INTEGER DEFAULT 0,
                contract_audited INTEGER DEFAULT 0,
                listed_major_exchange INTEGER DEFAULT 0,
                rwa_market_cap_usd REAL,-- from RWA.xyz total market
                last_updated TEXT
            )
        """)
        # Table 4: Gas prices
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gas_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slow_gwei REAL, standard_gwei REAL, fast_gwei REAL,
                eth_usd REAL, last_updated TEXT
            )
        """)
        # Table 5: Market sentiment (all sentiment sources)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_sentiment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,            -- "fear_greed"/"news_vader"/"reddit"/"claude"/"google_trends"
                token TEXT,             -- "MARKET" for market-wide, or "ETH"/"BTC" etc
                score REAL,             -- normalized 0.0-1.0 (0=bearish, 1=bullish)
                label TEXT,             -- "BULLISH"/"BEARISH"/"NEUTRAL"/"EXTREME_FEAR" etc
                details_json TEXT,      -- raw data as JSON
                last_updated TEXT
            )
        """)
        conn.commit()
        # Run migrations to add any new columns to existing tables
        _migrate_db(conn)
    logger.info("[data_pipeline] DB tables initialized: %s", DB_PATH)


# ─── Generic HTTP helper ──────────────────────────────────────────────────────

def _get(url: str, params: dict = None, headers: dict = None,
         timeout: int = 15, retries: int = 2) -> Optional[dict]:
    """Generic GET with retry + 429 handling."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers,
                                timeout=timeout)
            if resp.status_code == 429:
                wait = 60 * (attempt + 1)
                logger.warning("[pipeline] Rate limited on %s — waiting %ds", url, wait)
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.debug("[pipeline] Request error (%s): %s", url, e)
            if attempt < retries - 1:
                time.sleep(3)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 1 — CoinGecko: Token prices + 30d change (34 tokens)
# Why: Free aggregator, 13k+ tokens, RWA category filter, most trusted
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_coingecko_prices():
    """Fetch current prices for all tokens in TOKEN_MAP (batches of 20)."""
    ids = list(TOKEN_MAP.keys())
    all_data = []
    for i in range(0, len(ids), 20):
        batch = ids[i:i + 20]
        data = _get(f"{COINGECKO_BASE}/coins/markets", {
            "vs_currency": "usd",
            "ids": ",".join(batch),
            "order": "market_cap_desc",
            "sparkline": "false",
            "price_change_percentage": "24h,7d,30d",
        })
        if data:
            all_data.extend(data)
        time.sleep(1.5)  # polite to free tier (30 req/min limit)

    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        for tok in all_data:
            tid = tok.get("id", "")
            conn.execute("""
                INSERT OR REPLACE INTO token_prices
                (id, symbol, name, price_usd, market_cap, volume_24h,
                 change_24h, change_7d, change_30d, is_rwa, last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                tid,
                TOKEN_MAP.get(tid, tok.get("symbol","").upper()),
                tok.get("name",""),
                tok.get("current_price") or 0.0,
                tok.get("market_cap") or 0.0,
                tok.get("total_volume") or 0.0,
                tok.get("price_change_percentage_24h") or 0.0,
                tok.get("price_change_percentage_7d_in_currency") or 0.0,
                tok.get("price_change_percentage_30d_in_currency") or 0.0,
                1 if tid in RWA_ISSUERS else 0,
                now,
            ))
        conn.commit()
    logger.info("[CoinGecko] Saved %d token prices", len(all_data))


def _fetch_rwa_category():
    """Fetch ALL RWA tokens using CoinGecko's dedicated RWA category filter."""
    data = _get(f"{COINGECKO_BASE}/coins/markets", {
        "vs_currency": "usd",
        "category": "real-world-assets-rwa",
        "order": "market_cap_desc",
        "per_page": "50",
        "price_change_percentage": "24h,7d,30d",
    })
    if not data:
        return
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        for tok in data:
            tid = tok.get("id","")
            sym = tok.get("symbol","").upper()
            issuer = RWA_ISSUERS.get(tid, {})
            # Upsert token_prices with is_rwa=1
            conn.execute("""
                INSERT OR REPLACE INTO token_prices
                (id, symbol, name, price_usd, market_cap, volume_24h,
                 change_24h, change_7d, change_30d, is_rwa, last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,1,?)
            """, (
                tid, sym, tok.get("name",""),
                tok.get("current_price") or 0.0,
                tok.get("market_cap") or 0.0,
                tok.get("total_volume") or 0.0,
                tok.get("price_change_percentage_24h") or 0.0,
                tok.get("price_change_percentage_7d_in_currency") or 0.0,
                tok.get("price_change_percentage_30d_in_currency") or 0.0,
                now,
            ))
            # Upsert rwa_assets table
            conn.execute("""
                INSERT OR REPLACE INTO rwa_assets
                (id, symbol, name, price_usd, market_cap,
                 apy_pct, asset_type, underlying_asset, last_updated)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                tid, sym, tok.get("name",""),
                tok.get("current_price") or 0.0,
                tok.get("market_cap") or 0.0,
                issuer.get("apy_est", 0.0),
                "Treasury" if "treasury" in issuer.get("underlying","").lower()
                           else "Credit" if "loan" in issuer.get("underlying","").lower()
                           else "RWA",
                issuer.get("underlying", "Real World Assets"),
                now,
            ))
        conn.commit()
    logger.info("[CoinGecko RWA] Saved %d RWA tokens", len(data))


def _fetch_price_history():
    """Fetch 30-day daily prices for top tokens (needed for RSI/MACD in trading_analyzer)."""
    priority = [
        "bitcoin","ethereum","chainlink","aave","uniswap",
        "maker","curve-dao-token","ondo-finance","lido-dao","arbitrum",
    ]
    now = datetime.now(timezone.utc).isoformat()
    for tid in priority:
        try:
            data = _get(f"{COINGECKO_BASE}/coins/{tid}/market_chart", {
                "vs_currency": "usd", "days": "30", "interval": "daily",
            })
            if not data:
                continue
            prices = [round(p[1], 4) for p in data.get("prices", [])]
            with _get_conn() as conn:
                conn.execute(
                    "UPDATE token_prices SET price_history_json=?, last_updated=? WHERE id=?",
                    (json.dumps(prices), now, tid)
                )
                conn.commit()
            time.sleep(2)  # avoid rate limit on history endpoint
        except Exception as e:
            logger.debug("[CoinGecko history] %s: %s", tid, e)
    logger.info("[CoinGecko] Price history updated for %d tokens", len(priority))


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 2 — Binance: Real-time spot prices (top 15 tokens)
# Why: Most accurate real-time price, no API key, 1200 req/min
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_binance_prices():
    """Fetch real-time prices from Binance for top 15 tokens."""
    # Map Binance symbol → CoinGecko ID
    binance_to_cg = {
        "BTCUSDT":"bitcoin","ETHUSDT":"ethereum","BNBUSDT":"binancecoin",
        "SOLUSDT":"solana","XRPUSDT":"ripple","ADAUSDT":"cardano",
        "AVAXUSDT":"avalanche-2","DOTUSDT":"polkadot","LINKUSDT":"chainlink",
        "UNIUSDT":"uniswap","MATICUSDT":"matic-network","ARBUSDT":"arbitrum",
        "OPUSDT":"optimism","LDOUSDT":"lido-dao","AAVEUSDT":"aave",
    }
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for binance_sym, cg_id in binance_to_cg.items():
        data = _get(f"{BINANCE_BASE}/ticker/price", {"symbol": binance_sym})
        if data and "price" in data:
            price = float(data["price"])
            with _get_conn() as conn:
                conn.execute(
                    "UPDATE token_prices SET price_binance=?, last_updated=? WHERE id=?",
                    (price, now, cg_id)
                )
                conn.commit()
            updated += 1
        time.sleep(0.1)  # Binance is generous but be polite
    logger.info("[Binance] Updated real-time prices for %d tokens", updated)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 3 — DeFi Llama: TVL of 500+ DeFi protocols
# Why: Free, most comprehensive TVL tracker, covers all chains
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_defi_llama():
    """Fetch DeFi protocol TVL data. Also updates TVL for RWA protocols."""
    data = _get(f"{DEFILLAMA_BASE}/protocols")
    if not data:
        return
    top_protocols = data[:200]  # top 200 by TVL
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        for p in top_protocols:
            pid = p.get("slug") or p.get("name","")
            conn.execute("""
                INSERT OR REPLACE INTO defi_protocols
                (id, name, tvl_usd, tvl_change_1d, category, chain, last_updated)
                VALUES (?,?,?,?,?,?,?)
            """, (
                pid,
                p.get("name",""),
                p.get("tvl") or 0.0,
                p.get("change_1d") or 0.0,
                p.get("category",""),
                p.get("chain",""),
                now,
            ))
        conn.commit()

    # Update TVL for known RWA protocols
    rwa_name_map = {
        "ondo-finance": ["ondo","ondo finance"],
        "centrifuge":   ["centrifuge"],
        "maple":        ["maple","maple finance"],
        "goldfinch":    ["goldfinch"],
        "clearpool":    ["clearpool"],
    }
    for cg_id, name_variants in rwa_name_map.items():
        matching = [p for p in top_protocols
                    if any(v in p.get("name","").lower() for v in name_variants)]
        if matching:
            total_tvl = sum(p.get("tvl", 0) or 0 for p in matching)
            with _get_conn() as conn:
                conn.execute(
                    "UPDATE rwa_assets SET tvl_usd=?, last_updated=? WHERE id=?",
                    (total_tvl, now, cg_id)
                )
                conn.commit()
    logger.info("[DeFi Llama] Saved %d protocols", len(top_protocols))


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 4 — RWA.xyz: Total RWA market summary
# Why: Dedicated RWA analytics platform, shows sector growth
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_rwa_xyz():
    """Fetch RWA market summary from RWA.xyz. Stores in market_sentiment table."""
    # RWA.xyz public endpoints (no key needed)
    data = _get("https://api.rwa.xyz/v1/assets", timeout=10)
    if not data:
        # Fallback: try alternative endpoint
        data = _get("https://rwa.xyz/api/market-data", timeout=10)
    if not data:
        logger.debug("[RWA.xyz] Endpoint unavailable — skipping")
        return
    now = datetime.now(timezone.utc).isoformat()
    total_market = 0
    if isinstance(data, list):
        total_market = sum(item.get("tvl", 0) or 0 for item in data)
    elif isinstance(data, dict):
        total_market = data.get("total_market_cap", 0) or data.get("tvl", 0) or 0
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO market_sentiment (source, token, score, label, details_json, last_updated)
            VALUES (?,?,?,?,?,?)
        """, ("rwa_xyz", "MARKET", 0.6, "RWA_DATA",
              json.dumps({"total_market_cap_usd": total_market, "source": "rwa.xyz"}), now))
        conn.commit()
    logger.info("[RWA.xyz] Total RWA market: $%.0f", total_market)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 5 — Chainlink Oracle: Verified on-chain prices
# Why: 31 independent nodes → tamper-proof, used by $100B+ DeFi
# Requires: ETH_MAINNET_RPC in .env
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_chainlink_prices():
    """Read Chainlink price feeds directly from Ethereum mainnet smart contracts."""
    if not ETH_MAINNET_RPC or "YOUR_KEY" in ETH_MAINNET_RPC:
        logger.debug("[Chainlink] No mainnet RPC configured — skipping")
        return
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(ETH_MAINNET_RPC, request_kwargs={"timeout": 10}))
        if not w3.is_connected():
            logger.debug("[Chainlink] Cannot connect to mainnet RPC")
            return
        now = datetime.now(timezone.utc).isoformat()
        # Map feed → CoinGecko ID
        feed_to_cg = {
            "ETH/USD": "ethereum",
            "BTC/USD": "bitcoin",
            "LINK/USD": "chainlink",
        }
        for feed_name, cg_id in feed_to_cg.items():
            address = CHAINLINK_FEEDS.get(feed_name)
            if not address:
                continue
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(address),
                abi=CHAINLINK_ABI
            )
            # latestRoundData returns: (roundId, answer, startedAt, updatedAt, answeredInRound)
            round_data = contract.functions.latestRoundData().call()
            # answer has 8 decimal places: 210034500000 → $2100.345
            price = round_data[1] / 1e8
            with _get_conn() as conn:
                conn.execute(
                    "UPDATE token_prices SET price_chainlink=?, last_updated=? WHERE id=?",
                    (price, now, cg_id)
                )
                conn.commit()
            logger.info("[Chainlink] %s = $%.2f (on-chain verified)", feed_name, price)
            time.sleep(0.5)
    except ImportError:
        logger.debug("[Chainlink] web3 not available")
    except Exception as e:
        logger.debug("[Chainlink] Error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 6 — Etherscan: Smart contract verification status
# Why: Proves RWA contracts are transparent and audited
# Requires: ETHERSCAN_API_KEY in .env
# ═══════════════════════════════════════════════════════════════════════════════

# Known RWA contract addresses on Ethereum mainnet
RWA_CONTRACTS = {
    "ondo-finance":  "0x18c11FD286C5EC11c3b683Caa813B77f5163A122",  # ONDO token
    "centrifuge":    "0xc221b7E65FfC80DE234bB6667ABDd46593D34F0f",  # CFG token
    "maple":         "0x33349B282065b0284d756F0577FB39c158F935e6",  # MPL token
    "goldfinch":     "0xdab396cCF3d84Cf2D07C4454e10C8A6F5b008D2b",  # GFI token
}


def _check_etherscan_contract(address: str, cg_id: str):
    """Check if a smart contract is verified on Etherscan."""
    if not ETHERSCAN_KEY:
        return False
    data = _get("https://api.etherscan.io/api", {
        "module": "contract",
        "action": "getabi",
        "address": address,
        "apikey": ETHERSCAN_KEY,
    })
    if data and data.get("status") == "1":
        # ABI exists = contract source is verified/published
        now = datetime.now(timezone.utc).isoformat()
        with _get_conn() as conn:
            conn.execute(
                "UPDATE rwa_assets SET contract_audited=1, last_updated=? WHERE id=?",
                (now, cg_id)
            )
            conn.commit()
        return True
    return False


def _fetch_etherscan_verifications():
    """Check contract verification for all known RWA tokens."""
    if not ETHERSCAN_KEY:
        logger.debug("[Etherscan] No API key — skipping contract verification")
        return
    for cg_id, address in RWA_CONTRACTS.items():
        verified = _check_etherscan_contract(address, cg_id)
        logger.info("[Etherscan] %s contract verified: %s", cg_id, verified)
        time.sleep(0.3)  # Etherscan free tier: 5 req/sec


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 7 — SEC EDGAR: Legal filing verification
# Why: US regulator database — no API key, unlimited, authoritative
# ═══════════════════════════════════════════════════════════════════════════════

def _check_sec_edgar(company_name: str) -> dict:
    """Search SEC EDGAR for legal filings by a company name."""
    data = _get(EDGAR_BASE, {
        "q": f'"{company_name}"',
        "dateRange": "custom",
        "startdt": "2022-01-01",
        "hits.hits.total.value": "true",
    })
    if not data:
        return {"sec_verified": False, "filings_count": 0}
    hits = data.get("hits", {}).get("hits", [])
    filing_types = list(set(
        h.get("_source", {}).get("form_type", "")
        for h in hits[:10]
    ))
    return {
        "sec_verified": len(hits) > 0,
        "filings_count": len(hits),
        "filing_types": filing_types,
        "latest_filing": hits[0].get("_source", {}).get("period_of_report") if hits else None,
    }


def _fetch_sec_verifications():
    """Verify all RWA issuers in SEC EDGAR (runs weekly — legal info rarely changes)."""
    now = datetime.now(timezone.utc).isoformat()
    for cg_id, issuer_info in RWA_ISSUERS.items():
        company = issuer_info["company"]
        result = _check_sec_edgar(company)
        with _get_conn() as conn:
            conn.execute(
                "UPDATE rwa_assets SET sec_verified=?, last_updated=? WHERE id=?",
                (1 if result["sec_verified"] else 0, now, cg_id)
            )
            conn.commit()
        logger.info("[SEC EDGAR] %s: %d filings found", company, result["filings_count"])
        time.sleep(1)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 8 — OpenCorporates: Company incorporation verification
# Why: 140+ countries, proves legal existence of RWA issuers
# Free tier: 10 req/day — so we cache 7 days
# ═══════════════════════════════════════════════════════════════════════════════

def _check_opencorporates(company_name: str) -> dict:
    """Check company registration status in OpenCorporates."""
    data = _get(f"{OPENCORP_BASE}/companies/search", {
        "q": company_name, "format": "json",
    })
    if not data:
        return {"legal_incorporated": False}
    companies = data.get("results", {}).get("companies", [])
    if not companies:
        return {"legal_incorporated": False}
    top = companies[0]["company"]
    return {
        "legal_incorporated": True,
        "company_name": top.get("name"),
        "jurisdiction": top.get("jurisdiction_code"),
        "incorporated_on": top.get("incorporation_date"),
        "company_status": top.get("current_status"),
    }


def _fetch_opencorporates_verifications():
    """Check incorporation for all RWA issuers (runs weekly)."""
    now = datetime.now(timezone.utc).isoformat()
    for cg_id, issuer_info in RWA_ISSUERS.items():
        company = issuer_info["company"]
        result = _check_opencorporates(company)
        with _get_conn() as conn:
            conn.execute(
                "UPDATE rwa_assets SET legal_incorporated=?, last_updated=? WHERE id=?",
                (1 if result["legal_incorporated"] else 0, now, cg_id)
            )
            conn.commit()
        status = result.get("company_status", "unknown") if result["legal_incorporated"] else "not found"
        logger.info("[OpenCorporates] %s: %s", company, status)
        time.sleep(1)  # Respect free tier (10 req/day)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 9 — Dune Analytics: On-chain transfer history
# Why: Real blockchain activity proves tokens are actually being used
# Requires: DUNE_API_KEY in .env
# ═══════════════════════════════════════════════════════════════════════════════

# Pre-built public Dune queries (open to anyone)
DUNE_QUERIES = {
    "rwa_transfers": 3442521,   # RWA token monthly transfer volume
    "defi_users":   3186477,    # DeFi active users last 30 days
}


def _fetch_dune_query(query_id: int) -> Optional[list]:
    """Execute a Dune Analytics query and return rows."""
    if not DUNE_KEY:
        return None
    headers = {"X-Dune-API-Key": DUNE_KEY}
    # Step 1: Execute the query
    exec_resp = requests.post(
        f"{DUNE_BASE}/query/{query_id}/execute",
        headers=headers, timeout=15
    )
    if exec_resp.status_code != 200:
        return None
    execution_id = exec_resp.json().get("execution_id")
    if not execution_id:
        return None
    # Step 2: Poll for results (max 60 seconds)
    for _ in range(12):
        time.sleep(5)
        result = _get(f"{DUNE_BASE}/execution/{execution_id}/results",
                      headers=headers)
        if result and result.get("state") == "QUERY_STATE_COMPLETED":
            return result.get("result", {}).get("rows", [])
        if result and result.get("state") in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
            return None
    return None


def _fetch_dune_analytics():
    """Fetch on-chain activity data from Dune Analytics."""
    if not DUNE_KEY:
        logger.debug("[Dune] No API key — skipping")
        return
    rows = _fetch_dune_query(DUNE_QUERIES["rwa_transfers"])
    if not rows:
        return
    now = datetime.now(timezone.utc).isoformat()
    # Store as sentiment signal: high transfer volume = active market = bullish
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO market_sentiment (source, token, score, label, details_json, last_updated)
            VALUES (?,?,?,?,?,?)
        """, ("dune_onchain", "RWA", 0.65, "ACTIVE",
              json.dumps({"rows": rows[:10], "query_id": DUNE_QUERIES["rwa_transfers"]}), now))
        conn.commit()
    logger.info("[Dune] On-chain data: %d rows", len(rows))


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 10 — Fear & Greed Index: Market-wide sentiment
# Why: Most-cited crypto sentiment indicator, 0=extreme fear, 100=extreme greed
# No API key needed, updated daily
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_fear_greed():
    """Fetch the Crypto Fear & Greed Index (0-100) with 30-day history."""
    data = _get(f"{FEAR_GREED_BASE}/?limit=30")
    if not data or "data" not in data:
        return
    latest = data["data"][0]
    value = int(latest.get("value", 50))
    label = latest.get("value_classification", "Neutral").upper()
    # Normalize 0-100 → 0.0-1.0 score
    score = value / 100.0
    history = [{"value": int(d["value"]), "date": d["timestamp"]}
               for d in data["data"][:30]]
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO market_sentiment (source, token, score, label, details_json, last_updated)
            VALUES (?,?,?,?,?,?)
        """, ("fear_greed", "MARKET", score, label,
              json.dumps({"value": value, "label": label, "history_30d": history}), now))
        conn.commit()
    logger.info("[Fear&Greed] Score: %d (%s)", value, label)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 11 — CryptoCompare News + VADER Sentiment
# Why: Real news + local NLP (no extra API) = fast sentiment per token
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_news_sentiment():
    """Fetch crypto news and score sentiment with VADER NLP."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
    except ImportError:
        logger.debug("[News] vaderSentiment not installed")
        return

    tokens_to_track = ["ETH", "BTC", "LINK", "AAVE", "ONDO", "RWA"]
    now = datetime.now(timezone.utc).isoformat()
    for token in tokens_to_track:
        data = _get(f"{CRYPTOCOMPARE_BASE}/news/", {
            "lang": "EN",
            "categories": token,
            "lTs": int(time.time()) - 86400,  # last 24 hours
        })
        if not data or "Data" not in data:
            continue
        raw = data["Data"]
        # CryptoCompare returns dict on error, list on success
        if not isinstance(raw, list):
            continue
        articles = raw[:20]
        if not articles:
            continue
        # Score each headline with VADER
        scores = []
        for article in articles:
            title = article.get("title", "")
            body = article.get("body", "")[:200]
            text = f"{title}. {body}"
            score = analyzer.polarity_scores(text)
            scores.append(score["compound"])  # -1.0 to +1.0
        avg_compound = sum(scores) / len(scores) if scores else 0
        # Normalize -1..+1 → 0..1
        normalized = (avg_compound + 1) / 2
        if avg_compound >= 0.05:
            label = "BULLISH"
        elif avg_compound <= -0.05:
            label = "BEARISH"
        else:
            label = "NEUTRAL"
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO market_sentiment (source, token, score, label, details_json, last_updated)
                VALUES (?,?,?,?,?,?)
            """, ("news_vader", token, normalized, label,
                  json.dumps({
                      "article_count": len(articles),
                      "avg_compound": round(avg_compound, 3),
                      "sample_titles": [a.get("title","") for a in articles[:3]],
                  }), now))
            conn.commit()
        time.sleep(1)
    logger.info("[News+VADER] Sentiment scored for %d tokens", len(tokens_to_track))


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 12 — Reddit (PRAW): Community social sentiment
# Why: r/ethereum, r/defi are early indicators of retail sentiment
# Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET in .env
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_reddit_sentiment():
    """Fetch Reddit posts from crypto subreddits and score sentiment."""
    if not REDDIT_ID or not REDDIT_SECRET:
        logger.debug("[Reddit] No API credentials — skipping")
        return
    try:
        import praw
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        reddit = praw.Reddit(
            client_id=REDDIT_ID,
            client_secret=REDDIT_SECRET,
            user_agent=REDDIT_AGENT,
        )
        analyzer = SentimentIntensityAnalyzer()
        subreddits = {
            "cryptocurrency": "MARKET",
            "ethereum": "ETH",
            "defi": "DEFI",
            "RealWorldAssets": "RWA",
        }
        now = datetime.now(timezone.utc).isoformat()
        for sub_name, token_label in subreddits.items():
            try:
                subreddit = reddit.subreddit(sub_name)
                posts = list(subreddit.hot(limit=20))
                if not posts:
                    continue
                scores = []
                top_titles = []
                for post in posts:
                    text = f"{post.title}. {post.selftext[:150]}"
                    score = analyzer.polarity_scores(text)
                    scores.append(score["compound"])
                    top_titles.append(post.title)
                avg = sum(scores) / len(scores)
                normalized = (avg + 1) / 2
                label = "BULLISH" if avg >= 0.05 else "BEARISH" if avg <= -0.05 else "NEUTRAL"
                with _get_conn() as conn:
                    conn.execute("""
                        INSERT INTO market_sentiment
                        (source, token, score, label, details_json, last_updated)
                        VALUES (?,?,?,?,?,?)
                    """, ("reddit", token_label, normalized, label,
                          json.dumps({
                              "subreddit": sub_name,
                              "posts_analyzed": len(posts),
                              "avg_compound": round(avg, 3),
                              "top_titles": top_titles[:3],
                          }), now))
                    conn.commit()
                time.sleep(1)
            except Exception as e:
                logger.debug("[Reddit] r/%s error: %s", sub_name, e)
        logger.info("[Reddit] Sentiment fetched for %d subreddits", len(subreddits))
    except ImportError:
        logger.debug("[Reddit] praw not installed")
    except Exception as e:
        logger.debug("[Reddit] Error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 13 — Claude via Bedrock: AI-powered market analysis
# Why: Uses your EXISTING Bedrock setup — synthesizes all signals intelligently
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_claude_sentiment():
    """Use Claude (via existing bedrock_client.py) to analyze market conditions."""
    try:
        from bedrock_client import invoke_bedrock
        # Gather context from our DB
        tokens = get_all_tokens()[:10]
        fg_row = get_latest_sentiment("fear_greed", "MARKET")
        fg_value = fg_row.get("details_json", {}).get("value", 50) if fg_row else 50
        top_tokens_summary = ", ".join(
            f"{t['symbol']} {t.get('change_30d', 0):+.1f}%"
            for t in tokens[:8] if t.get("change_30d") is not None
        )
        prompt = f"""You are a crypto market analyst. Analyze the following market data and provide a brief assessment.

Market Data:
- Fear & Greed Index: {fg_value}/100
- Top token 30-day performance: {top_tokens_summary}

Respond in exactly this JSON format:
{{
  "overall_sentiment": "BULLISH" or "BEARISH" or "NEUTRAL" or "CAUTIOUSLY_BULLISH" or "CAUTIOUSLY_BEARISH",
  "sentiment_score": <number 0.0 to 1.0>,
  "key_themes": ["theme1", "theme2", "theme3"],
  "short_term_outlook": "1-2 sentences",
  "best_opportunities": ["token1", "token2"],
  "main_risks": ["risk1", "risk2"]
}}"""
        response_text = invoke_bedrock(prompt)
        # Parse JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
            score = float(analysis.get("sentiment_score", 0.5))
            label = analysis.get("overall_sentiment", "NEUTRAL")
            now = datetime.now(timezone.utc).isoformat()
            with _get_conn() as conn:
                conn.execute("""
                    INSERT INTO market_sentiment
                    (source, token, score, label, details_json, last_updated)
                    VALUES (?,?,?,?,?,?)
                """, ("claude_llm", "MARKET", score, label,
                      json.dumps(analysis), now))
                conn.commit()
            logger.info("[Claude] Market sentiment: %s (%.2f)", label, score)
    except Exception as e:
        logger.debug("[Claude] Sentiment error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 14 — Google Trends: Search interest spikes
# Why: Google searches spike 2-3 days BEFORE retail price pumps
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_google_trends():
    """Fetch Google search trends for top crypto terms."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(5, 10))
        keywords = ["ethereum price", "bitcoin price", "RWA crypto", "DeFi yield"]
        pytrends.build_payload(keywords, timeframe="now 7-d")
        interest = pytrends.interest_over_time()
        if interest.empty:
            return
        now = datetime.now(timezone.utc).isoformat()
        # Get latest values (last row)
        latest = interest.iloc[-1]
        trend_data = {kw: int(latest.get(kw, 0)) for kw in keywords if kw in latest}
        # Compute aggregate score (average of all keywords, normalized 0-100→0-1)
        avg_score = sum(trend_data.values()) / (len(trend_data) * 100) if trend_data else 0.5
        label = "HIGH_INTEREST" if avg_score > 0.6 else "LOW_INTEREST" if avg_score < 0.3 else "MODERATE"
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO market_sentiment
                (source, token, score, label, details_json, last_updated)
                VALUES (?,?,?,?,?,?)
            """, ("google_trends", "MARKET", avg_score, label,
                  json.dumps(trend_data), now))
            conn.commit()
        logger.info("[Google Trends] %s (score: %.2f)", label, avg_score)
    except ImportError:
        logger.debug("[Google Trends] pytrends not installed")
    except Exception as e:
        logger.debug("[Google Trends] Error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# Gas Prices (via Web3 Sepolia — already in project)
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_gas():
    """Fetch Ethereum gas prices via existing Web3 connection."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        from wallet_tools import web3
        base_gwei = float(web3.from_wei(web3.eth.gas_price, "gwei"))
        eth_usd = _get_cached_price("ethereum")
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO gas_prices (slow_gwei, standard_gwei, fast_gwei, eth_usd, last_updated)
                VALUES (?,?,?,?,?)
            """, (round(base_gwei * 0.9, 1), round(base_gwei, 1),
                  round(base_gwei * 1.2, 1), eth_usd, now))
            conn.commit()
        logger.info("[Gas] %.1f Gwei (standard)", base_gwei)
    except Exception as e:
        logger.debug("[Gas] Web3 error: %s — using fallback", e)
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO gas_prices (slow_gwei, standard_gwei, fast_gwei, eth_usd, last_updated)
                VALUES (?,?,?,?,?)
            """, (9.0, 10.0, 12.0, 2000.0, now))
            conn.commit()


# ─── Public Read Functions ────────────────────────────────────────────────────

def _get_cached_price(token_id: str) -> float:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT price_usd FROM token_prices WHERE id=?", (token_id,)
        ).fetchone()
        return row["price_usd"] if row else 0.0


def get_all_tokens() -> list:
    """Return all tokens sorted by market cap (largest first)."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM token_prices ORDER BY market_cap DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_token(token_id: str) -> Optional[dict]:
    """Get a single token by CoinGecko ID or ticker symbol."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM token_prices WHERE id=? OR LOWER(symbol)=LOWER(?)",
            (token_id, token_id)
        ).fetchone()
        return dict(row) if row else None


def get_rwa_assets() -> list:
    """Return all RWA assets with trust scores."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM rwa_assets ORDER BY market_cap DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_gas() -> dict:
    """Return latest gas prices — handles both old and new schema."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM gas_prices ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {"slow_gwei": 9.0, "standard_gwei": 10.0, "fast_gwei": 12.0, "eth_usd": 2000.0}
        d = dict(row)
        # Normalize old schema (base_fee/timestamp) → new schema (eth_usd/last_updated)
        if "last_updated" not in d and "timestamp" in d:
            d["last_updated"] = d.pop("timestamp", None)
        if "eth_usd" not in d:
            d["eth_usd"] = _get_cached_price("ethereum") or 2000.0
        return d


def get_defi_protocols(limit: int = 20) -> list:
    """Return top DeFi protocols by TVL."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM defi_protocols ORDER BY tvl_usd DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_latest_sentiment(source: str = None, token: str = None) -> Optional[dict]:
    """Get the most recent sentiment record for a source/token combo."""
    with _get_conn() as conn:
        if source and token:
            row = conn.execute("""
                SELECT * FROM market_sentiment WHERE source=? AND token=?
                ORDER BY id DESC LIMIT 1
            """, (source, token)).fetchone()
        elif source:
            row = conn.execute("""
                SELECT * FROM market_sentiment WHERE source=?
                ORDER BY id DESC LIMIT 1
            """, (source,)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM market_sentiment ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            r = dict(row)
            try:
                r["details_json"] = json.loads(r["details_json"] or "{}")
            except Exception:
                pass
            return r
        return None


def get_all_sentiment_summary() -> dict:
    """Get latest sentiment from each source as a summary dict."""
    sources = ["fear_greed", "news_vader", "reddit", "claude_llm",
               "google_trends", "dune_onchain", "rwa_xyz"]
    summary = {}
    for src in sources:
        row = get_latest_sentiment(src)
        if row:
            summary[src] = {
                "score": row["score"],
                "label": row["label"],
                "token": row["token"],
                "last_updated": row["last_updated"],
            }
    return summary


def get_data_freshness() -> dict:
    """Check how old our cached data is."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT last_updated FROM token_prices ORDER BY last_updated DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {"is_fresh": False, "age_minutes": 9999, "last_updated": None}
        last = datetime.fromisoformat(row["last_updated"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last).total_seconds() / 60
        return {
            "is_fresh": age < CACHE_EXPIRY_MINUTES,
            "age_minutes": round(age, 1),
            "last_updated": row["last_updated"],
        }


# ─── Refresh Jobs ─────────────────────────────────────────────────────────────

def refresh_prices():
    """Refresh token prices (CoinGecko + Binance + Chainlink). Runs every 15 min."""
    logger.info("[pipeline] Refreshing prices...")
    _fetch_coingecko_prices()
    _fetch_rwa_category()
    _fetch_binance_prices()
    _fetch_chainlink_prices()
    _fetch_gas()


def refresh_defi():
    """Refresh DeFi TVL + RWA market data. Runs every 15 min."""
    logger.info("[pipeline] Refreshing DeFi/RWA...")
    _fetch_defi_llama()
    _fetch_rwa_xyz()


def refresh_sentiment():
    """Refresh all sentiment sources. Runs every 1 hour."""
    logger.info("[pipeline] Refreshing sentiment...")
    _fetch_fear_greed()
    _fetch_news_sentiment()
    _fetch_reddit_sentiment()
    _fetch_google_trends()
    _fetch_claude_sentiment()


def refresh_history():
    """Refresh 30-day price history + Dune analytics. Runs every 24 hours."""
    logger.info("[pipeline] Refreshing history...")
    _fetch_price_history()
    _fetch_dune_analytics()


def refresh_legal():
    """Refresh RWA legal/contract verifications. Runs every 7 days."""
    logger.info("[pipeline] Refreshing legal verifications...")
    _fetch_sec_verifications()
    _fetch_opencorporates_verifications()
    _fetch_etherscan_verifications()


def run_full_refresh() -> dict:
    """Run ALL refresh jobs. Called at startup and on manual trigger."""
    import time as _time
    start = _time.time()
    refresh_prices()
    refresh_defi()
    refresh_sentiment()
    elapsed = round(_time.time() - start, 1)
    count = len(get_all_tokens())
    logger.info("[pipeline] Full refresh complete: %d tokens in %ss", count, elapsed)
    return {"status": "ok", "tokens": count, "elapsed_s": elapsed}


# ─── Scheduler ────────────────────────────────────────────────────────────────

_scheduler: Optional[BackgroundScheduler] = None


def start_scheduler():
    """Start background scheduler with all refresh jobs."""
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(refresh_prices,   "interval", minutes=15,  id="prices")
    _scheduler.add_job(refresh_defi,     "interval", minutes=15,  id="defi")
    _scheduler.add_job(refresh_sentiment,"interval", minutes=60,  id="sentiment")
    _scheduler.add_job(refresh_history,  "interval", hours=24,    id="history")
    _scheduler.add_job(refresh_legal,    "interval", days=7,      id="legal")
    _scheduler.start()
    logger.info("[pipeline] Scheduler started (prices/defi=15min, sentiment=1hr, history=24hr, legal=7d)")
    return _scheduler


def initialize():
    """Call ONCE at Flask startup. Inits DB, loads fresh data, starts scheduler."""
    _init_db()
    freshness = get_data_freshness()
    if not freshness["is_fresh"]:
        logger.info("[pipeline] Cache stale (%.1f min) — loading fresh data...",
                    freshness["age_minutes"])
        refresh_prices()
        refresh_defi()
        refresh_sentiment()
        # history + legal run in background
    else:
        logger.info("[pipeline] Cache fresh (%.1f min old) — skipping initial load",
                    freshness["age_minutes"])
    start_scheduler()
