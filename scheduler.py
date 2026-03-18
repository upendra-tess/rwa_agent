"""
scheduler.py — Background Cache Refresh Scheduler
===================================================
Periodically runs the market-level agents (macro, industry, financial,
cashflow, geopolitical, market) and stores their outputs in agent_cache.

This means user requests read from cache (milliseconds) instead of
calling live APIs + LLMs (30-60 seconds).

Usage:
  from scheduler import start_scheduler, refresh_cache_now

  # Start background scheduler (runs every 30 min)
  start_scheduler(interval_minutes=30)

  # Or manually trigger a refresh
  refresh_cache_now()
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from agent_cache import cache
from data_sources import fetch_rwa_universe
from agents import (
    macro_analysis_agent,
    industry_analysis_agent,
    financial_analysis_agent,
    cashflow_analysis_agent,
    geopolitical_analysis_agent,
    market_analysis_agent,
)

logger = logging.getLogger(__name__)

# Configurable refresh interval (default 30 minutes)
REFRESH_INTERVAL_MINUTES = int(os.environ.get("CACHE_REFRESH_MINUTES", "30"))

# Lock to prevent concurrent refreshes
_refresh_lock = threading.Lock()
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_running = False


def refresh_cache_now() -> dict:
    """
    Run all market-level agents and store results in cache.
    Returns a status dict with timing info.

    This is the core function — called by the scheduler and
    can also be triggered manually via API endpoint.
    """
    if not _refresh_lock.acquire(blocking=False):
        logger.warning("[Scheduler] Refresh already in progress, skipping")
        return {"status": "SKIPPED", "reason": "refresh already in progress"}

    try:
        start_time = time.time()
        logger.info("[Scheduler] ═══ Cache refresh starting ═══")
        results = {}

        # Step 1: Fetch RWA universe (used by downstream agents)
        logger.info("[Scheduler] Fetching RWA universe...")
        t0 = time.time()
        rwa_universe = fetch_rwa_universe()
        cache.set("rwa_universe", rwa_universe)
        results["rwa_universe"] = {
            "count": len(rwa_universe),
            "time_seconds": round(time.time() - t0, 1),
        }
        logger.info("[Scheduler] RWA universe: %d protocols (%.1fs)",
                    len(rwa_universe), time.time() - t0)

        # Step 2: Build a dummy state for agents
        # (no customer profile needed — agents produce market-level output)
        dummy_state = {
            "user_input": "",
            "rwa_universe": rwa_universe,
            "customer_profile": {
                "budget": 100000,
                "region": "GLOBAL",
                "time_horizon_months": 12,
                "expected_return_pct": 10.0,
                "redemption_window": "monthly",
                "risk_tolerance": "moderate",
            },
            "macro_context": {},
            "industry_analysis": {},
            "financial_analysis": {},
            "cashflow_analysis": {},
            "geopolitical_analysis": {},
            "market_analysis": {},
            "matched_assets": [],
            "asset_class_analysis": {},
            "filtered_assets": [],
            "result": "",
        }

        # Step 3: Run macro analysis first (other agents depend on it)
        logger.info("[Scheduler] Running macro_analysis...")
        t0 = time.time()
        macro_result = macro_analysis_agent(dummy_state)
        macro_context = macro_result.get("macro_context", {})
        cache.set("macro_context", macro_context)
        dummy_state["macro_context"] = macro_context
        results["macro_context"] = {"time_seconds": round(time.time() - t0, 1)}
        logger.info("[Scheduler] macro_analysis done (%.1fs)", time.time() - t0)

        # Step 4: Run 5 parallel agents
        parallel_agents = {
            "industry_analysis": industry_analysis_agent,
            "financial_analysis": financial_analysis_agent,
            "cashflow_analysis": cashflow_analysis_agent,
            "geopolitical_analysis": geopolitical_analysis_agent,
            "market_analysis": market_analysis_agent,
        }

        threads = {}
        agent_results = {}

        def _run_agent(name, fn):
            try:
                t = time.time()
                result = fn(dummy_state)
                agent_results[name] = result.get(name, result)
                results[name] = {"time_seconds": round(time.time() - t, 1)}
                logger.info("[Scheduler] %s done (%.1fs)", name, time.time() - t)
            except Exception as e:
                logger.error("[Scheduler] %s failed: %s", name, e)
                results[name] = {"error": str(e)}

        for name, fn in parallel_agents.items():
            t = threading.Thread(target=_run_agent, args=(name, fn), daemon=True)
            threads[name] = t
            t.start()

        # Wait for all to complete (timeout 120s)
        for name, t in threads.items():
            t.join(timeout=120)

        # Step 5: Store all results in cache
        for name, result in agent_results.items():
            cache.set(name, result)

        total_time = round(time.time() - start_time, 1)
        logger.info("[Scheduler] ═══ Cache refresh complete (%.1fs) ═══", total_time)

        return {
            "status": "OK",
            "total_time_seconds": total_time,
            "agents": results,
            "cache_warm": cache.is_warm(),
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("[Scheduler] Refresh failed: %s", e, exc_info=True)
        return {"status": "ERROR", "error": str(e)}

    finally:
        _refresh_lock.release()


def _scheduler_loop(interval_minutes: int):
    """Background loop that periodically refreshes the cache."""
    global _scheduler_running
    interval_seconds = interval_minutes * 60

    logger.info("[Scheduler] Background scheduler started (every %d min)", interval_minutes)

    while _scheduler_running:
        try:
            refresh_cache_now()
        except Exception as e:
            logger.error("[Scheduler] Loop error: %s", e)

        # Sleep in small increments so we can stop quickly
        for _ in range(interval_seconds):
            if not _scheduler_running:
                break
            time.sleep(1)


def start_scheduler(interval_minutes: int = None, warmup: bool = True):
    """
    Start the background cache refresh scheduler.

    Parameters
    ----------
    interval_minutes : int
        How often to refresh (default from CACHE_REFRESH_MINUTES env var, or 30)
    warmup : bool
        If True, run an immediate refresh before starting the loop.
        This ensures the cache is warm before any user requests.
    """
    global _scheduler_thread, _scheduler_running

    if _scheduler_running:
        logger.warning("[Scheduler] Already running")
        return

    if interval_minutes is None:
        interval_minutes = REFRESH_INTERVAL_MINUTES

    _scheduler_running = True

    if warmup:
        logger.info("[Scheduler] Warming up cache on startup...")
        refresh_cache_now()

    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(interval_minutes,),
        daemon=True,
        name="CacheScheduler",
    )
    _scheduler_thread.start()
    logger.info("[Scheduler] Background thread started")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running
    _scheduler_running = False
    logger.info("[Scheduler] Scheduler stopped")
