"""
server.py - FastAPI WebSocket server bridging the RWA Multi-Agent to the UI.

Now with Agent Memory:
  - Background scheduler pre-computes market-level agent outputs every 30 min
  - User requests use the FAST graph (reads from cache, skips live API + LLM)
  - Endpoints: /ws/rwa (WebSocket), /cache/status, /cache/refresh

Protocol (JSON messages over WebSocket):
  Server → Client:
    { "type": "question",   "text": "..." }       # profiler asks a question
    { "type": "thinking",   "text": "..." }        # pipeline progress
    { "type": "node_start", "node": "...", "label": "..." }
    { "type": "node_done",  "node": "...", "label": "..." }
    { "type": "result",     "text": "..." }        # final analysis output
    { "type": "error",      "text": "..." }

  Client → Server:
    { "type": "answer", "text": "..." }            # user reply to profiler
"""

import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agents.conversational_profiler import ConversationalProfiler
from agents import (
    macro_analysis_agent,
    industry_analysis_agent,
    financial_analysis_agent,
    cashflow_analysis_agent,
    geopolitical_analysis_agent,
    market_analysis_agent,
    match_asset_agent,
    asset_class_analysis_agent,
    asset_analysis_agent,
)
from agent_cache import cache
from scheduler import start_scheduler, refresh_cache_now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="RWA Multi-Agent Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# Startup: warm cache + start scheduler
# ═══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Start the background cache scheduler on server startup."""
    logger.info("[Server] Starting background cache scheduler...")
    # Start in a thread so it doesn't block the server startup
    import threading
    threading.Thread(
        target=start_scheduler,
        kwargs={"interval_minutes": 30, "warmup": True},
        daemon=True,
    ).start()


# ═══════════════════════════════════════════════════════════════════════════════
# REST Endpoints: Cache management
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/cache/status")
async def cache_status():
    """Check the status of all cached agent outputs."""
    return {
        "cache_warm": cache.is_warm(),
        "entries": cache.cache_status(),
    }


@app.post("/cache/refresh")
async def cache_refresh():
    """Manually trigger a cache refresh."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, refresh_cache_now)
    return result


@app.get("/health")
async def health():
    return {"status": "ok", "cache_warm": cache.is_warm()}


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket: Node labels and details
# ═══════════════════════════════════════════════════════════════════════════════

NODE_LABELS = {
    "customer_profiling":   "Customer Profiling Agent",
    "macro_analysis":       "Macro Analysis Agent",
    "industry_analysis":    "Industry Analysis Agent",
    "financial_analysis":   "Financial Analysis Agent",
    "cashflow_analysis":    "Cash Flow Agent",
    "geopolitical_analysis":"Geopolitical Analysis Agent",
    "market_analysis":      "Market Analysis Agent",
    "match_asset":          "Asset Match Agent",
    "asset_class_analysis": "Asset Class Analysis Agent",
    "asset_analysis":       "Asset Analysis Agent",
}

NODE_START_DETAIL = {
    "customer_profiling": "Structured investor profile from conversation — budget, region, risk, horizon, target return",
    "macro_analysis":     "Fetching macro signals: interest rates, inflation, credit spreads, USD strength, yield curve",
    "match_asset":        "Screening RWA universe — filtering by region, risk tolerance, liquidity window and return target",
    "asset_class_analysis": "Deep-diving shortlisted asset classes: real-estate debt, trade finance, private credit, commodities",
    "asset_analysis":     "Scoring individual RWA tokens on fundamentals, on-chain metrics, counterparty risk, and yield quality",
}

NODE_DONE_DETAIL = {
    "customer_profiling": "Profile complete — investor preferences locked in",
    "macro_analysis":     "Macro context ready — identified key rate and credit environment drivers",
    "match_asset":        "Asset shortlist generated — top candidates selected against profile",
    "asset_class_analysis": "Asset class scores computed — risk-adjusted rankings produced",
    "asset_analysis":     "Final token analysis complete — personalised recommendations ready",
}


async def send(ws: WebSocket, msg: dict):
    await ws.send_text(json.dumps(msg))


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket: Main session handler
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/rwa")
async def rwa_session(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket session started")

    try:
        profiler = ConversationalProfiler()

        # Step 1: Conversational profiling
        opening = profiler.start()
        await send(ws, {"type": "question", "text": opening})

        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            if data.get("type") != "answer":
                continue
            user_text = data.get("text", "").strip()
            if not user_text:
                continue

            message, complete = profiler.respond(user_text)
            await send(ws, {"type": "question", "text": message})
            if complete:
                break

        profile = profiler.get_profile()
        profile["_from_conversation"] = True
        logger.info("Profile collected: budget=%.0f region=%s risk=%s",
                    profile["budget"], profile["region"], profile["risk_tolerance"])

        # Step 2: Check if cache is warm → use FAST path
        use_cache = cache.is_warm()

        if use_cache:
            logger.info("[Server] Cache is WARM — using fast path (skipping 6 agents)")
            await send(ws, {
                "type": "thinking",
                "text": "Using pre-computed market intelligence (cached) — running personalized analysis..."
            })
        else:
            logger.info("[Server] Cache is COLD — using full pipeline (all agents)")
            await send(ws, {
                "type": "thinking",
                "text": "Running full market analysis across specialized agents…"
            })

        # Build initial state
        initial_state = {
            "user_input": "",
            "rwa_universe": [],
            "customer_profile": profile,
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

        loop = asyncio.get_event_loop()

        if use_cache:
            # ══════════════════════════════════════════════════════════
            # FAST PATH: Inject cached data, skip 6 agents
            # ══════════════════════════════════════════════════════════
            cached_state = cache.get_all_cached_state()
            initial_state.update(cached_state)

            # Emit cached agent completions (instant)
            cached_agents = [
                "macro_analysis", "industry_analysis", "financial_analysis",
                "cashflow_analysis", "geopolitical_analysis", "market_analysis",
            ]
            for node in cached_agents:
                label = NODE_LABELS.get(node, node)
                await send(ws, {"type": "node_start", "node": node, "label": label, "detail": f"Loading from cache..."})
                await send(ws, {"type": "node_done", "node": node, "label": label, "detail": f"Loaded from pre-computed cache"})

            state = initial_state

        else:
            # ══════════════════════════════════════════════════════════
            # FULL PATH: Run all agents live
            # ══════════════════════════════════════════════════════════
            def ns(node): return {"type": "node_start", "node": node, "label": NODE_LABELS[node], "detail": NODE_START_DETAIL.get(node, "")}
            def nd(node): return {"type": "node_done",  "node": node, "label": NODE_LABELS[node], "detail": NODE_DONE_DETAIL.get(node, "")}

            state = initial_state

            await send(ws, ns("macro_analysis"))
            state = await loop.run_in_executor(None, macro_analysis_agent, state)
            await send(ws, nd("macro_analysis"))

            # 5 parallel agents
            PARALLEL = [
                ("industry_analysis",    industry_analysis_agent,     "Industry Analysis Agent",    "Scanning sector trends, tokenisation activity, and issuer quality across RWA verticals"),
                ("financial_analysis",   financial_analysis_agent,    "Financial Analysis Agent",   "Evaluating yield spreads, LTV ratios, default probabilities, and financial health of issuers"),
                ("cashflow_analysis",    cashflow_analysis_agent,     "Cash Flow Agent",            "Modelling cash flow schedules, redemption windows, and liquidity risk of shortlisted assets"),
                ("geopolitical_analysis",geopolitical_analysis_agent, "Geopolitical Analysis Agent","Assessing jurisdiction risk, regulatory environment, and cross-border capital flow restrictions"),
                ("market_analysis",      market_analysis_agent,       "Market Analysis Agent",      "Analysing on-chain trading volumes, secondary market depth, and token price stability"),
            ]

            for node, _, label, detail in PARALLEL:
                await send(ws, {"type": "node_start", "node": node, "label": label, "detail": detail})

            async def run_parallel_agent(node, fn, label, done_detail):
                result = await loop.run_in_executor(None, fn, state)
                await send(ws, {"type": "node_done", "node": node, "label": label, "detail": done_detail})
                return result

            DONE_DETAILS = {
                "industry_analysis":    "Sector analysis complete — issuer quality and tokenisation trends mapped",
                "financial_analysis":   "Financial analysis complete — yield and credit metrics scored",
                "cashflow_analysis":    "Cash flow analysis complete — liquidity profiles established",
                "geopolitical_analysis":"Geopolitical analysis complete — jurisdiction risk assessed",
                "market_analysis":      "Market analysis complete — on-chain liquidity and price stability scored",
            }

            results = await asyncio.gather(*[
                run_parallel_agent(node, fn, label, DONE_DETAILS[node])
                for node, fn, label, _ in PARALLEL
            ])

            for r in results:
                state = {**state, **r}

        # ══════════════════════════════════════════════════════════
        # COMMON PATH: Run user-specific agents
        # ══════════════════════════════════════════════════════════
        def ns(node): return {"type": "node_start", "node": node, "label": NODE_LABELS[node], "detail": NODE_START_DETAIL.get(node, "")}
        def nd(node): return {"type": "node_done",  "node": node, "label": NODE_LABELS[node], "detail": NODE_DONE_DETAIL.get(node, "")}

        # customer_profiling already done via conversation
        await send(ws, ns("customer_profiling"))
        await send(ws, nd("customer_profiling"))

        await send(ws, ns("match_asset"))
        state = await loop.run_in_executor(None, match_asset_agent, state)
        await send(ws, nd("match_asset"))

        await send(ws, ns("asset_class_analysis"))
        state = await loop.run_in_executor(None, asset_class_analysis_agent, state)
        await send(ws, nd("asset_class_analysis"))

        await send(ws, ns("asset_analysis"))
        state = await loop.run_in_executor(None, asset_analysis_agent, state)
        await send(ws, nd("asset_analysis"))

        result = state.get("result", "No result generated.")
        await send(ws, {"type": "result", "text": result})
        logger.info("Session completed successfully (cache=%s)", "HIT" if use_cache else "MISS")

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error("Session error: %s", e, exc_info=True)
        try:
            await send(ws, {"type": "error", "text": f"An error occurred: {e}"})
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
