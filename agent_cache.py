"""
agent_cache.py — Agent Memory / Pre-computed Cache
====================================================
SQLite-backed cache that stores pre-computed agent outputs so that
user requests can skip live API calls and LLM inference for
market-level (non-user-specific) agents.

Cached (market-level, refreshed on schedule):
  - rwa_universe         (DeFiLlama RWA protocols)
  - macro_context        (treasury yields, FRED, IMF, ECB, etc.)
  - industry_analysis    (sector trends, tokenisation activity)
  - financial_analysis   (yield spreads, credit conditions)
  - cashflow_analysis    (cash flow schedules, liquidity)
  - geopolitical_analysis (jurisdiction risk, regulatory)
  - market_analysis      (on-chain volumes, price stability)

NOT cached (user-specific, always run live):
  - customer_profiling
  - match_asset
  - asset_class_analysis
  - asset_analysis
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("AGENT_CACHE_DB", "agent_cache.db")

# Default TTLs in seconds
DEFAULT_TTL = 1800       # 30 minutes
RWA_UNIVERSE_TTL = 300   # 5 minutes (changes frequently)
MACRO_TTL = 3600         # 1 hour (slow-moving data)

CACHE_KEYS = {
    "rwa_universe":          RWA_UNIVERSE_TTL,
    "macro_context":         MACRO_TTL,
    "industry_analysis":     DEFAULT_TTL,
    "financial_analysis":    DEFAULT_TTL,
    "cashflow_analysis":     DEFAULT_TTL,
    "geopolitical_analysis": DEFAULT_TTL,
    "market_analysis":       DEFAULT_TTL,
}


class AgentCache:
    """SQLite-backed agent output cache."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create the cache table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_cache (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    cached_at  REAL NOT NULL,
                    ttl        INTEGER NOT NULL
                )
            """)
            conn.commit()
        logger.info("[AgentCache] Initialized at %s", self.db_path)

    def get(self, key: str) -> Optional[Any]:
        """
        Get a cached value. Returns None if key doesn't exist or is stale.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value, cached_at, ttl FROM agent_cache WHERE key = ?",
                (key,),
            ).fetchone()

        if not row:
            return None

        value_json, cached_at, ttl = row
        age = time.time() - cached_at

        if age > ttl:
            logger.debug("[AgentCache] Key '%s' is stale (age=%.0fs, ttl=%ds)", key, age, ttl)
            return None

        try:
            return json.loads(value_json)
        except json.JSONDecodeError:
            logger.warning("[AgentCache] Failed to decode key '%s'", key)
            return None

    def set(self, key: str, value: Any, ttl: int = None):
        """Store a value in the cache."""
        if ttl is None:
            ttl = CACHE_KEYS.get(key, DEFAULT_TTL)

        value_json = json.dumps(value, default=str)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO agent_cache (key, value, cached_at, ttl)
                   VALUES (?, ?, ?, ?)""",
                (key, value_json, time.time(), ttl),
            )
            conn.commit()

        logger.debug("[AgentCache] Stored '%s' (ttl=%ds, size=%d bytes)",
                     key, ttl, len(value_json))

    def is_fresh(self, key: str) -> bool:
        """Check if a cached value exists and is within its TTL."""
        return self.get(key) is not None

    def get_all_cached_state(self) -> Dict[str, Any]:
        """
        Get all cached agent outputs as a dict suitable for injecting
        into the LangGraph pipeline state.
        """
        state = {}
        for key in CACHE_KEYS:
            value = self.get(key)
            if value is not None:
                state[key] = value
        return state

    def is_warm(self) -> bool:
        """Check if ALL cacheable keys have fresh data."""
        return all(self.is_fresh(key) for key in CACHE_KEYS)

    def cache_status(self) -> Dict[str, Any]:
        """Return status of all cache entries."""
        status = {}
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key, cached_at, ttl FROM agent_cache"
            ).fetchall()

        now = time.time()
        for key, cached_at, ttl in rows:
            age = now - cached_at
            status[key] = {
                "fresh": age <= ttl,
                "age_seconds": round(age),
                "ttl_seconds": ttl,
                "cached_at": datetime.fromtimestamp(cached_at, tz=timezone.utc).isoformat(),
                "expires_in": max(0, round(ttl - age)),
            }

        # Add missing keys
        for key in CACHE_KEYS:
            if key not in status:
                status[key] = {"fresh": False, "age_seconds": None, "cached_at": None}

        return status

    def clear(self):
        """Clear all cached data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM agent_cache")
            conn.commit()
        logger.info("[AgentCache] Cache cleared")


# Global singleton
cache = AgentCache()
