"""
api.py — Flask REST API for RWA Agent
=======================================
Endpoints:
  POST /api/chat                    → full agent pipeline (risk → macro)
  POST /api/risk/profile            → customer risk profiling only
  POST /api/macro/analyze           → full macro analysis (all 5 sub-agents)
  GET  /api/macro/industry          → industry analysis only
  GET  /api/macro/financial         → financial analysis only
  GET  /api/macro/cashflow          → cash flow analysis only
  GET  /api/macro/geopolitical      → geopolitical analysis only
  GET  /api/macro/market            → market analysis only
  GET  /api/health                  → health check
"""

import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

from agent_graph import build_graph
from agents.macro_analysis import (
    run_macro_analysis,
    run_industry_analysis,
    run_financial_analysis,
    run_cash_flow_analysis,
    run_geopolitical_analysis,
    run_market_analysis,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

agent = build_graph()
logger.info("[api] LangGraph agent built")


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: Extract risk profile from request
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_profile(data: dict) -> dict:
    """Extract customer risk profile from request body."""
    return {
        "risk_tolerance": data.get("risk_tolerance", "moderate"),
        "investment_horizon": data.get("investment_horizon", "medium"),
        "target_roi_pct": float(data.get("target_roi_pct", 15.0)),
        "budget_usd": float(data.get("budget_usd", 10000.0)),
        "preferred_asset_types": data.get("preferred_asset_types", ["RWA"]),
        "jurisdiction": data.get("jurisdiction", "US"),
        "kyc_status": data.get("kyc_status", "verified"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Main Chat Endpoint (full pipeline)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Run the full agent pipeline: Customer Risk Profiling → Macro Analysis.
    Body: { "message": "I want 20% ROI with $10k budget" }
    """
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "No message provided."}), 400

    initial_state = {
        "user_input": message,
        "session_id": data.get("session_id", ""),
        "result": "",
    }

    try:
        final_state = agent.invoke(initial_state)
    except Exception as err:
        logger.error("[api] Agent error: %s", err, exc_info=True)
        return jsonify({
            "error": f"Agent error: {err}",
            "result": f"Agent error: {err}",
        }), 500

    return jsonify({
        "result": final_state.get("result", "No response."),
        "customer_risk_profile": final_state.get("customer_risk_profile", {}),
        "macro_analysis_report": final_state.get("macro_analysis_report", {}),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Customer Risk Profiling Endpoint
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/risk/profile", methods=["POST"])
def risk_profile():
    """
    Run customer risk profiling only.
    Body: { "message": "I'm conservative, want stable returns" }
    """
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "No message provided."}), 400

    from agent_graph import customer_risk_profiling
    state = {"user_input": message}
    result = customer_risk_profiling(state)

    return jsonify({
        "customer_risk_profile": result.get("customer_risk_profile", {}),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Macro Analysis Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/macro/analyze", methods=["POST"])
def macro_analyze():
    """
    Run all 5 macro analysis sub-agents.
    Body: {
        "risk_tolerance": "moderate",
        "investment_horizon": "medium",
        "target_roi_pct": 15,
        "budget_usd": 10000,
        "jurisdiction": "US"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        profile = _extract_profile(data)
        report = run_macro_analysis(customer_risk_profile=profile)
        return jsonify(report)
    except Exception as e:
        logger.error("[api] macro_analyze: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/macro/industry", methods=["GET", "POST"])
def macro_industry():
    """Run industry analysis sub-agent only."""
    try:
        data = request.get_json(silent=True) or {}
        profile = _extract_profile(data) if data else {}
        result = run_industry_analysis(customer_risk_profile=profile or None)
        return jsonify(result)
    except Exception as e:
        logger.error("[api] macro_industry: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/macro/financial", methods=["GET", "POST"])
def macro_financial():
    """Run financial analysis sub-agent only."""
    try:
        data = request.get_json(silent=True) or {}
        profile = _extract_profile(data) if data else {}
        result = run_financial_analysis(customer_risk_profile=profile or None)
        return jsonify(result)
    except Exception as e:
        logger.error("[api] macro_financial: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/macro/cashflow", methods=["GET", "POST"])
def macro_cashflow():
    """Run cash flow analysis sub-agent only."""
    try:
        data = request.get_json(silent=True) or {}
        profile = _extract_profile(data) if data else {}
        result = run_cash_flow_analysis(customer_risk_profile=profile or None)
        return jsonify(result)
    except Exception as e:
        logger.error("[api] macro_cashflow: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/macro/geopolitical", methods=["GET", "POST"])
def macro_geopolitical():
    """Run geopolitical analysis sub-agent only."""
    try:
        data = request.get_json(silent=True) or {}
        profile = _extract_profile(data) if data else {}
        result = run_geopolitical_analysis(customer_risk_profile=profile or None)
        return jsonify(result)
    except Exception as e:
        logger.error("[api] macro_geopolitical: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/macro/market", methods=["GET", "POST"])
def macro_market():
    """Run market analysis sub-agent only."""
    try:
        data = request.get_json(silent=True) or {}
        profile = _extract_profile(data) if data else {}
        result = run_market_analysis(customer_risk_profile=profile or None)
        return jsonify(result)
    except Exception as e:
        logger.error("[api] macro_market: %s", e)
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "agents": {
            "customer_risk_profiling": "active",
            "macro_analysis": "active",
            "sub_agents": [
                "industry_analysis",
                "financial_analysis",
                "cash_flow_analysis",
                "geopolitical_analysis",
                "market_analysis",
            ],
        },
        "pipeline": "customer_risk → macro_analysis → [match_asset → ...]",
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n[api] Starting RWA Agent API on http://localhost:5000")
    print("[api] Endpoints:")
    print("  POST /api/chat                  → full pipeline")
    print("  POST /api/risk/profile          → risk profiling only")
    print("  POST /api/macro/analyze         → all 5 macro agents")
    print("  GET  /api/macro/industry        → industry analysis")
    print("  GET  /api/macro/financial       → financial analysis")
    print("  GET  /api/macro/cashflow        → cash flow analysis")
    print("  GET  /api/macro/geopolitical    → geopolitical analysis")
    print("  GET  /api/macro/market          → market analysis")
    print("  GET  /api/health                → health check")
    print()
    app.run(host="0.0.0.0", port=5000, debug=False)
