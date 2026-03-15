"""
api.py — Flask REST API
========================
Endpoints:
  POST /api/chat              → main agent chat (all intents)
  GET  /api/wallet/agent-info → agent wallet address + balance
  GET  /api/health            → health check

  NEW trading endpoints:
  GET  /api/market/status     → Fear & Greed + top movers
  GET  /api/market/analyze    → full portfolio analysis (query: roi, budget)
  GET  /api/market/token/:id  → single token deep analysis
  GET  /api/market/gas        → current gas prices
  GET  /api/rwa/verify/:id    → RWA trust verification report
  GET  /api/rwa/list          → all RWA tokens with trust scores
  POST /api/trade/plan        → build trade execution plan (body: roi, budget)
  GET  /api/data/refresh      → trigger manual data refresh
  GET  /api/data/freshness    → how old is our market data
"""

import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

from agent_graph import build_graph
from wallet_tools import web3, AGENT_ADDRESS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

agent = build_graph()
logger.info("[api] LangGraph agent built (%d nodes)", 10)


# ═══════════════════════════════════════════════════════════════════════════════
# Original Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/wallet/agent-info", methods=["GET"])
def get_agent_info():
    try:
        balance_wei = web3.eth.get_balance(AGENT_ADDRESS)
        balance_eth = float(web3.from_wei(balance_wei, "ether"))
        return jsonify({"agent_address": AGENT_ADDRESS, "agent_balance": balance_eth})
    except Exception as err:
        return jsonify({"agent_address": AGENT_ADDRESS, "error": str(err)})


@app.route("/api/chat", methods=["POST"])
def chat():
    data         = request.get_json(silent=True) or {}
    message      = data.get("message", "").strip()
    user_address = data.get("user_address", "").strip()

    if not message:
        return jsonify({"error": "No message provided."}), 400

    initial_state = {
        "user_input":   message,
        "intent":       "",
        "amount":       "",
        "user_address": user_address,
        "token_id":     "",
        "roi_target":   "",
        "result":       "",
    }

    try:
        final_state = agent.invoke(initial_state)
    except Exception as err:
        logger.error("[api] Agent error: %s", err, exc_info=True)
        return jsonify({
            "intent":        "unknown",
            "amount":        "",
            "result":        f"Agent error: {err}",
            "agent_address": AGENT_ADDRESS,
        }), 500

    return jsonify({
        "intent":        final_state.get("intent", "unknown"),
        "amount":        final_state.get("amount", ""),
        "token_id":      final_state.get("token_id", ""),
        "roi_target":    final_state.get("roi_target", ""),
        "result":        final_state.get("result", "No response."),
        "agent_address": AGENT_ADDRESS,
    })


@app.route("/api/health", methods=["GET"])
def health():
    from data_pipeline import get_data_freshness
    try:
        freshness = get_data_freshness()
    except Exception:
        freshness = {"is_fresh": False, "age_minutes": -1}
    return jsonify({
        "status":        "ok",
        "agent_address": AGENT_ADDRESS,
        "data_fresh":    freshness["is_fresh"],
        "data_age_min":  freshness["age_minutes"],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# NEW: Market Intelligence Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/market/status", methods=["GET"])
def market_status():
    """Fear & Greed index + top gainers/losers + sentiment summary."""
    try:
        from data_pipeline import (
            get_all_tokens, get_latest_sentiment,
            get_all_sentiment_summary, get_data_freshness, get_gas
        )

        tokens    = get_all_tokens()
        fg_row    = get_latest_sentiment("fear_greed", "MARKET")
        fg_details = fg_row.get("details_json", {}) if fg_row else {}
        fg_value  = fg_details.get("value", 50) if isinstance(fg_details, dict) else 50
        fg_label  = fg_row.get("label", "UNKNOWN") if fg_row else "UNKNOWN"
        gas       = get_gas()
        freshness = get_data_freshness()
        sentiment = get_all_sentiment_summary()

        with_change = [t for t in tokens if t.get("change_24h") is not None]
        gainers = sorted(with_change, key=lambda x: x["change_24h"], reverse=True)[:5]
        losers  = sorted(with_change, key=lambda x: x["change_24h"])[:5]

        return jsonify({
            "fear_greed": {
                "value": fg_value,
                "label": fg_label,
            },
            "gas": gas,
            "gainers_24h": [
                {"symbol": t["symbol"], "change_24h": t["change_24h"],
                 "price_usd": t["price_usd"]} for t in gainers
            ],
            "losers_24h": [
                {"symbol": t["symbol"], "change_24h": t["change_24h"],
                 "price_usd": t["price_usd"]} for t in losers
            ],
            "sentiment_sources": sentiment,
            "tokens_total":      len(tokens),
            "data_fresh":        freshness["is_fresh"],
            "data_age_min":      freshness["age_minutes"],
        })
    except Exception as e:
        logger.error("[api] market_status: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/market/analyze", methods=["GET"])
def market_analyze():
    """
    Full token ranking + portfolio allocation.
    Query params: roi (default 20), budget (default 1000), top_n (default 8)
    """
    try:
        from trading_analyzer import analyze_all_tokens

        roi_target = float(request.args.get("roi", 20))
        budget     = float(request.args.get("budget", 1000))
        top_n      = int(request.args.get("top_n", 8))

        report = analyze_all_tokens(
            roi_target_pct=roi_target,
            budget_usd=budget,
            top_n=top_n,
        )
        return jsonify(report)
    except Exception as e:
        logger.error("[api] market_analyze: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/market/token/<token_id>", methods=["GET"])
def token_analysis(token_id: str):
    """Deep analysis of a single token by CoinGecko ID."""
    try:
        from trading_analyzer import analyze_token
        analysis = analyze_token(token_id)
        if not analysis:
            return jsonify({"error": f"Token '{token_id}' not found"}), 404
        return jsonify(analysis)
    except Exception as e:
        logger.error("[api] token_analysis %s: %s", token_id, e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/market/gas", methods=["GET"])
def gas_prices():
    """Current Ethereum gas prices."""
    try:
        from data_pipeline import get_gas
        return jsonify(get_gas())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# NEW: RWA Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/rwa/verify/<token_id>", methods=["GET"])
def rwa_verify(token_id: str):
    """Run full 5-check trust verification on a RWA token."""
    try:
        from verification_layer import verify_rwa_asset
        report = verify_rwa_asset(token_id)
        return jsonify(report)
    except Exception as e:
        logger.error("[api] rwa_verify %s: %s", token_id, e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/rwa/list", methods=["GET"])
def rwa_list():
    """List all RWA tokens with their latest trust scores from DB."""
    try:
        from data_pipeline import get_rwa_assets
        from verification_layer import get_all_rwa_trust_summary

        assets = get_rwa_assets()
        trust  = {t["token_id"]: t for t in get_all_rwa_trust_summary()}

        result = []
        for a in assets:
            tid = a.get("id", "")
            t   = trust.get(tid, {})
            result.append({
                "id":          tid,
                "symbol":      a.get("symbol"),
                "name":        a.get("name"),
                "price_usd":   a.get("price_usd"),
                "market_cap":  a.get("market_cap"),
                "tvl_usd":     a.get("tvl_usd"),
                "apy_pct":     a.get("apy_pct"),
                "trust_score": t.get("trust_score", 0),
                "trust_badge": t.get("trust_badge", "UNVERIFIED"),
            })

        result.sort(key=lambda x: x["trust_score"], reverse=True)
        return jsonify({"rwa_tokens": result, "count": len(result)})
    except Exception as e:
        logger.error("[api] rwa_list: %s", e)
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# NEW: Trade Plan Endpoint
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/trade/plan", methods=["POST"])
def trade_plan():
    """
    Build a complete gas/slippage-aware trade execution plan.
    Body: { "roi_target": 20, "budget": 1000 }
    """
    try:
        from trading_strategy import get_full_trading_plan

        data       = request.get_json(silent=True) or {}
        roi_target = float(data.get("roi_target", 20))
        budget     = float(data.get("budget", 1000))

        plan = get_full_trading_plan(
            roi_target_pct=roi_target,
            budget_usd=budget,
        )
        return jsonify(plan)
    except Exception as e:
        logger.error("[api] trade_plan: %s", e)
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# NEW: Data Management Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/data/refresh", methods=["GET"])
def data_refresh():
    """Trigger a manual data refresh in the background."""
    def _refresh():
        try:
            from data_pipeline import (
                _fetch_coingecko_prices, _fetch_rwa_category,
                _fetch_defi_llama, _fetch_fear_greed, _fetch_news_sentiment
            )
            import time
            _fetch_coingecko_prices()
            time.sleep(1)
            _fetch_rwa_category()
            _fetch_defi_llama()
            _fetch_fear_greed()
            _fetch_news_sentiment()
            logger.info("[api] Background data refresh complete")
        except Exception as e:
            logger.error("[api] Background refresh error: %s", e)

    t = threading.Thread(target=_refresh, daemon=True)
    t.start()
    return jsonify({"status": "refresh_started", "message": "Data refresh running in background"})


@app.route("/api/data/freshness", methods=["GET"])
def data_freshness():
    """Check how old the market data is."""
    try:
        from data_pipeline import get_data_freshness
        return jsonify(get_data_freshness())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# Background scheduler — refresh data every 15 minutes
# ═══════════════════════════════════════════════════════════════════════════════

def _start_background_scheduler():
    """Start a background thread to refresh market data periodically."""
    import time

    def _scheduler():
        time.sleep(60)  # Wait 60s after startup before first refresh
        while True:
            try:
                from data_pipeline import (
                    _fetch_coingecko_prices, _fetch_rwa_category,
                    _fetch_defi_llama, _fetch_fear_greed
                )
                logger.info("[api] Scheduled data refresh starting...")
                _fetch_coingecko_prices()
                time.sleep(2)
                _fetch_rwa_category()
                _fetch_defi_llama()
                _fetch_fear_greed()
                logger.info("[api] Scheduled data refresh complete")
            except Exception as e:
                logger.error("[api] Scheduler error: %s", e)
            time.sleep(900)  # 15 minutes

    t = threading.Thread(target=_scheduler, daemon=True)
    t.start()
    logger.info("[api] Background data scheduler started (15 min interval)")


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Initialize DB and seed data on startup
    try:
        from data_pipeline import _init_db, _fetch_coingecko_prices, _fetch_fear_greed
        _init_db()
        _fetch_coingecko_prices()
        _fetch_fear_greed()
        logger.info("[api] Initial data seeded")
    except Exception as e:
        logger.warning("[api] Initial seed warning: %s", e)

    _start_background_scheduler()

    print("\n[api] Starting Flask server on http://localhost:5000")
    print("[api] Endpoints:")
    print("  POST /api/chat")
    print("  GET  /api/market/status")
    print("  GET  /api/market/analyze?roi=20&budget=1000")
    print("  GET  /api/market/token/<id>")
    print("  GET  /api/rwa/list")
    print("  GET  /api/rwa/verify/<id>")
    print("  POST /api/trade/plan")
    print("  GET  /api/data/refresh")
    print()
    app.run(host="0.0.0.0", port=5000, debug=False)
