"""
trading_strategy.py — Trade Execution Strategy Engine
======================================================
Takes ranked picks from trading_analyzer.py and converts them into
concrete, executable trade plans with gas + slippage protection.

Responsibilities:
  1. Trade Plan:      Entry/exit prices, position sizing, order type
  2. Gas Guard:       Only execute when gas < max_gwei threshold
  3. Slippage Guard:  Max 0.5% price impact (rejects if larger)
  4. DCA Strategy:    Split budget into weekly buys to reduce risk
  5. Stop-Loss/TP:    Auto stop-loss (-10%) and take-profit (+20%) levels
  6. Portfolio Rebal: Monitor existing positions, rebalance if needed

Public API:
  build_trade_plan(analysis_report, budget_usd)    → ExecutionPlan dict
  check_gas_feasibility(trade_usd)                 → gas cost in USD + feasibility
  estimate_slippage(token_id, trade_usd)           → slippage % estimate
  get_dca_schedule(budget_usd, weeks)              → weekly DCA amounts
  build_stop_take_levels(entry_price, roi_target)  → stop-loss/take-profit prices
  format_plan_for_chat(plan)                       → human-readable string
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
MAX_GAS_GWEI         = 50.0    # reject trade if gas > 50 Gwei
MAX_SLIPPAGE_PCT     = 0.5     # reject if price impact > 0.5%
STOP_LOSS_PCT        = -10.0   # auto stop-loss at -10% from entry
DEFAULT_TAKE_PROFIT  = 20.0    # default take-profit = ROI target
MIN_TRADE_USD        = 10.0    # minimum viable trade size
GAS_UNITS_ERC20      = 65_000  # typical ERC-20 transfer gas units
GAS_UNITS_UNISWAP    = 150_000 # typical Uniswap v3 swap gas units
UNISWAP_FEE_PCT      = 0.30    # Uniswap v3 0.3% pool fee (most RWA tokens)
UNISWAP_V3_ROUTER    = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
COINGECKO_BASE       = "https://api.coingecko.com/api/v3"

# Token → DEX routing (where to buy each token)
TOKEN_DEX_ROUTE = {
    "bitcoin":           "Coinbase",      # BTC: CEX only
    "ethereum":          "Uniswap V3",    # ETH: native
    "chainlink":         "Uniswap V3",
    "aave":              "Uniswap V3",
    "uniswap":           "Uniswap V3",
    "maker":             "Uniswap V3",
    "curve-dao-token":   "Uniswap V3",
    "lido-dao":          "Uniswap V3",
    "arbitrum":          "Uniswap V3",
    "optimism":          "Uniswap V3",
    "ondo-finance":      "Uniswap V3",
    "centrifuge":        "Uniswap V3",
    "maple":             "Uniswap V3",
    "goldfinch":         "Uniswap V3",
    "clearpool":         "Uniswap V3",
    "pendle":            "Uniswap V3",
    "gains-network":     "Uniswap V3",
    "gmx":               "GMX DEX",
}

# Uniswap V3 pool fee tiers per token (0.05%, 0.3%, 1%)
TOKEN_POOL_FEE = {
    "ethereum":        500,    # 0.05% — highest liquidity
    "bitcoin":         500,
    "chainlink":       3000,   # 0.3%
    "aave":            3000,
    "uniswap":         3000,
    "maker":           3000,
    "ondo-finance":    3000,
    "centrifuge":      10000,  # 1% — lower liquidity RWA
    "maple":           10000,
    "goldfinch":       10000,
    "clearpool":       10000,
}


# ─── HTTP helper ──────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code in (404, 429):
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("[strategy] HTTP %s: %s", url, e)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Gas Guard — Check if trading is economically viable
# ═══════════════════════════════════════════════════════════════════════════════

def check_gas_feasibility(trade_usd: float,
                          is_swap: bool = True) -> dict:
    """
    Check if a trade is economically viable given current gas prices.

    Args:
        trade_usd: size of trade in USD
        is_swap:   True for DEX swap, False for simple ERC-20 transfer

    Returns:
        dict with: gas_gwei, gas_usd, fee_pct, is_feasible, recommendation
    """
    from data_pipeline import get_gas
    gas = get_gas()

    standard_gwei = gas.get("standard_gwei", 10.0) or 10.0
    eth_usd       = gas.get("eth_usd") or 2000.0

    gas_units = GAS_UNITS_UNISWAP if is_swap else GAS_UNITS_ERC20

    # Gas cost in USD
    gas_eth = (standard_gwei * 1e-9) * gas_units
    gas_usd = gas_eth * eth_usd
    fee_pct = (gas_usd / trade_usd * 100) if trade_usd > 0 else 999

    # Uniswap fee
    dex_fee_usd = trade_usd * (UNISWAP_FEE_PCT / 100) if is_swap else 0
    total_cost_usd = gas_usd + dex_fee_usd
    total_fee_pct  = (total_cost_usd / trade_usd * 100) if trade_usd > 0 else 999

    # Decision
    if standard_gwei > MAX_GAS_GWEI:
        status = "GAS_TOO_HIGH"
        recommendation = f"Gas is {standard_gwei:.0f} Gwei (max={MAX_GAS_GWEI}). Wait for lower gas."
        is_feasible = False
    elif total_fee_pct > 2.0:
        status = "FEES_TOO_HIGH"
        recommendation = (
            f"Total fees {total_fee_pct:.1f}% of trade "
            f"(gas=${gas_usd:.2f} + DEX=${dex_fee_usd:.2f}). "
            f"Increase trade size or wait for lower gas."
        )
        is_feasible = False
    elif total_fee_pct > 1.0:
        status = "FEES_HIGH"
        recommendation = (
            f"Fees {total_fee_pct:.1f}% — acceptable but high. "
            f"Consider larger trade size."
        )
        is_feasible = True
    else:
        status = "OK"
        recommendation = (
            f"Gas OK: {standard_gwei:.1f} Gwei, "
            f"total fees ${total_cost_usd:.2f} ({total_fee_pct:.2f}%)"
        )
        is_feasible = True

    return {
        "gas_gwei":        standard_gwei,
        "gas_eth":         round(gas_eth, 8),
        "gas_usd":         round(gas_usd, 4),
        "dex_fee_usd":     round(dex_fee_usd, 4),
        "total_cost_usd":  round(total_cost_usd, 4),
        "total_fee_pct":   round(total_fee_pct, 3),
        "is_feasible":     is_feasible,
        "status":          status,
        "recommendation":  recommendation,
        "eth_usd":         eth_usd,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Slippage Guard
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_slippage(token_id: str, trade_usd: float) -> dict:
    """
    Estimate price impact (slippage) for a given trade size.

    Uses CoinGecko 24h volume to approximate market depth.
    Rule of thumb: slippage ≈ trade_size / (daily_volume × 0.05)
    (assuming 5% of daily volume available in top-of-book liquidity)

    Args:
        token_id:  CoinGecko token ID
        trade_usd: USD value of the trade

    Returns:
        dict with: slippage_pct, is_acceptable, recommendation
    """
    from data_pipeline import get_token
    token = get_token(token_id)

    volume_24h = (token.get("volume_24h", 0) or 0) if token else 0

    if volume_24h <= 0:
        # No volume data — flag as uncertain
        return {
            "slippage_pct":  None,
            "is_acceptable": None,
            "volume_24h":    0,
            "status":        "NO_VOLUME_DATA",
            "recommendation": "Cannot estimate slippage — no volume data. Use limit order.",
        }

    # Estimated on-chain DEX liquidity = 5% of daily volume
    dex_liquidity = volume_24h * 0.05
    # Price impact = sqrt(trade / liquidity) × 100 (constant product AMM formula)
    import math
    slippage_pct = (math.sqrt(trade_usd / dex_liquidity) * 100
                    if dex_liquidity > 0 else 99)
    slippage_pct = round(slippage_pct, 3)

    if slippage_pct > 2.0:
        status = "SLIPPAGE_CRITICAL"
        is_acceptable = False
        recommendation = (
            f"Slippage ~{slippage_pct:.2f}% — TOO HIGH. "
            f"Split into {int(slippage_pct / MAX_SLIPPAGE_PCT) + 1} smaller trades "
            f"or use TWAP over multiple hours."
        )
    elif slippage_pct > MAX_SLIPPAGE_PCT:
        status = "SLIPPAGE_HIGH"
        is_acceptable = False
        recommendation = (
            f"Slippage ~{slippage_pct:.2f}% exceeds {MAX_SLIPPAGE_PCT}% max. "
            f"Reduce trade size or split into 2-3 trades."
        )
    elif slippage_pct > 0.2:
        status = "SLIPPAGE_MODERATE"
        is_acceptable = True
        recommendation = (
            f"Slippage ~{slippage_pct:.2f}% — acceptable. "
            f"Set Uniswap slippage tolerance to {min(1.0, slippage_pct * 2):.1f}%."
        )
    else:
        status = "SLIPPAGE_LOW"
        is_acceptable = True
        recommendation = f"Slippage ~{slippage_pct:.2f}% — very low. Safe to trade."

    return {
        "token_id":        token_id,
        "trade_usd":       trade_usd,
        "volume_24h":      volume_24h,
        "estimated_dex_liquidity": round(dex_liquidity, 0),
        "slippage_pct":    slippage_pct,
        "is_acceptable":   is_acceptable,
        "status":          status,
        "recommendation":  recommendation,
        "uniswap_tolerance": min(1.0, max(0.1, slippage_pct * 2)),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DCA Schedule — Dollar Cost Averaging
# ═══════════════════════════════════════════════════════════════════════════════

def get_dca_schedule(budget_usd: float, weeks: int = 4,
                     market_fear_greed: int = 50) -> dict:
    """
    Build a DCA (Dollar-Cost Averaging) schedule.

    Logic:
      - In EXTREME FEAR (< 20):  buy more now (contrarian), 40% first week
      - In FEAR (20-40):         equal weekly splits
      - In NEUTRAL (40-60):      equal weekly splits
      - In GREED (> 60):         buy less now, wait for pullback

    Args:
        budget_usd:         total budget in USD
        weeks:              number of weeks to spread purchases
        market_fear_greed:  current Fear & Greed value (0-100)

    Returns:
        dict with schedule (date, amount, rationale)
    """
    today = datetime.now(timezone.utc)
    schedule = []

    if market_fear_greed < 20:
        # Extreme Fear: contrarian — buy more now while prices are low
        weights = _distribute_contrarian(weeks)
        strategy = "CONTRARIAN_BUY"
        rationale = (
            f"Extreme Fear (F&G={market_fear_greed}) = historically good buy zone. "
            "Weighting earlier purchases higher."
        )
    elif market_fear_greed < 40:
        # Fear: equal splits — cautious
        weights = [1.0 / weeks] * weeks
        strategy = "EQUAL_DCA"
        rationale = (
            f"Fear market (F&G={market_fear_greed}). "
            "Equal weekly purchases to average entry price."
        )
    elif market_fear_greed <= 60:
        # Neutral: equal splits
        weights = [1.0 / weeks] * weeks
        strategy = "EQUAL_DCA"
        rationale = (
            f"Neutral market (F&G={market_fear_greed}). "
            "Standard equal DCA schedule."
        )
    else:
        # Greed: delayed — wait for better prices
        weights = _distribute_delayed(weeks)
        strategy = "DELAYED_ENTRY"
        rationale = (
            f"Greed/Overbought market (F&G={market_fear_greed}). "
            "Delaying purchases — waiting for pullback."
        )

    total_weight = sum(weights)
    for i, w in enumerate(weights):
        buy_date = today + timedelta(weeks=i)
        amount   = round(budget_usd * (w / total_weight), 2)
        schedule.append({
            "week":    i + 1,
            "date":    buy_date.strftime("%Y-%m-%d"),
            "amount_usd": amount,
            "weight_pct": round((w / total_weight) * 100, 1),
        })

    return {
        "strategy":       strategy,
        "total_budget":   budget_usd,
        "weeks":          weeks,
        "fear_greed":     market_fear_greed,
        "rationale":      rationale,
        "schedule":       schedule,
        "avg_entry_note": (
            "DCA reduces timing risk — you buy at the average price "
            "over the period rather than risking one bad entry point."
        ),
    }


def _distribute_contrarian(weeks: int) -> list:
    """More weight on earlier purchases (buy the dip)."""
    weights = []
    for i in range(weeks):
        weights.append(weeks - i)
    return weights


def _distribute_delayed(weeks: int) -> list:
    """Less weight on early purchases (wait for pullback)."""
    weights = []
    for i in range(weeks):
        weights.append(i + 1)
    return weights


# ═══════════════════════════════════════════════════════════════════════════════
# Stop-Loss / Take-Profit Levels
# ═══════════════════════════════════════════════════════════════════════════════

def build_stop_take_levels(entry_price: float,
                           roi_target_pct: float = DEFAULT_TAKE_PROFIT,
                           risk_label: str = "MEDIUM") -> dict:
    """
    Calculate stop-loss and take-profit price levels.

    Stop-loss varies by risk:
      LOW risk:    -8%  (tight stop — stable assets)
      MEDIUM risk: -12% (moderate stop)
      HIGH risk:   -15% (wider stop — volatile assets)
      VERY_HIGH:   -20% (widest — speculative positions)

    Take-profit levels (scaled to ROI target):
      TP1 = 50% of target (partial exit)
      TP2 = 100% of target (full exit / core target)
      TP3 = 150% of target (stretch goal — hold remainder)
    """
    stop_pcts = {
        "LOW":       -8.0,
        "MEDIUM":   -12.0,
        "HIGH":     -15.0,
        "VERY_HIGH": -20.0,
    }
    stop_pct = stop_pcts.get(risk_label, -12.0)

    stop_loss_price  = round(entry_price * (1 + stop_pct / 100), 8)
    tp1_price = round(entry_price * (1 + (roi_target_pct * 0.5) / 100), 8)
    tp2_price = round(entry_price * (1 + roi_target_pct / 100), 8)
    tp3_price = round(entry_price * (1 + (roi_target_pct * 1.5) / 100), 8)

    return {
        "entry_price":    entry_price,
        "stop_loss":      stop_loss_price,
        "stop_loss_pct":  stop_pct,
        "tp1_price":      tp1_price,
        "tp1_pct":        roi_target_pct * 0.5,
        "tp1_action":     "Sell 33% of position",
        "tp2_price":      tp2_price,
        "tp2_pct":        roi_target_pct,
        "tp2_action":     "Sell 50% of remaining position",
        "tp3_price":      tp3_price,
        "tp3_pct":        roi_target_pct * 1.5,
        "tp3_action":     "Hold remaining — stretch target",
        "risk_reward_ratio": round(abs(roi_target_pct / stop_pct), 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Main Trade Plan Builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_trade_plan(analysis_report: dict,
                     budget_usd: float = 1000.0) -> dict:
    """
    Build a complete executable trade plan from trading_analyzer output.

    For each BUY/ACCUMULATE token:
      1. Gas feasibility check
      2. Slippage estimation
      3. Stop-loss + take-profit levels
      4. DCA schedule (if market fear)
      5. Execution order (which to buy first)

    Args:
        analysis_report: output of trading_analyzer.analyze_all_tokens()
        budget_usd:      total budget in USD

    Returns:
        ExecutionPlan dict with all trades ready to execute
    """
    start = time.time()
    fg_value = analysis_report.get("market_context", {}).get("fear_greed_value", 50)
    roi_target = analysis_report.get("roi_target_pct", 20.0)
    warnings = list(analysis_report.get("warnings", []))

    portfolio = analysis_report.get("portfolio", {})
    allocations = portfolio.get("allocations", [])

    if not allocations:
        return {
            "status":   "NO_TRADES",
            "message":  portfolio.get("message", "No viable trades under current conditions"),
            "trades":   [],
            "warnings": warnings,
            "dca_schedule": get_dca_schedule(budget_usd, 4, fg_value),
            "market_context": analysis_report.get("market_context", {}),
        }

    trades = []
    total_gas_usd = 0
    execution_priority = 1

    for alloc in allocations:
        token_id  = alloc["token_id"]
        symbol    = alloc["symbol"]
        alloc_usd = alloc["alloc_usd"]
        buy_price = alloc["buy_price"]
        risk_label = alloc["risk_label"]

        # 1. Gas check
        gas_check = check_gas_feasibility(alloc_usd, is_swap=True)
        total_gas_usd += gas_check["gas_usd"]

        # 2. Slippage estimate
        slippage = estimate_slippage(token_id, alloc_usd)

        # 3. Stop-loss / take-profit
        levels = build_stop_take_levels(buy_price, roi_target, risk_label)

        # 4. DEX routing
        dex = TOKEN_DEX_ROUTE.get(token_id, "Uniswap V3")
        pool_fee_bps = TOKEN_POOL_FEE.get(token_id, 3000)

        # 5. Net amount after fees
        net_usd = alloc_usd - gas_check["total_cost_usd"]
        qty_after_fees = net_usd / buy_price if buy_price > 0 else 0

        # 6. Overall feasibility
        is_viable = (gas_check["is_feasible"] and
                     (slippage["is_acceptable"] is not False) and
                     alloc_usd >= MIN_TRADE_USD)

        if not is_viable:
            if not gas_check["is_feasible"]:
                warnings.append(
                    f"{symbol}: Trade blocked — {gas_check['recommendation']}")
            if slippage["is_acceptable"] is False:
                warnings.append(
                    f"{symbol}: Slippage risk — {slippage['recommendation']}")

        trade = {
            "execution_priority": execution_priority,
            "token_id":           token_id,
            "symbol":             symbol,
            "action":             "BUY",
            "dex":                dex,
            "pool_fee_bps":       pool_fee_bps,

            # Amounts
            "gross_usd":          alloc_usd,
            "gas_usd":            gas_check["gas_usd"],
            "dex_fee_usd":        gas_check["dex_fee_usd"],
            "total_fees_usd":     gas_check["total_cost_usd"],
            "net_usd":            round(net_usd, 2),

            # Prices
            "entry_price":        buy_price,
            "quantity":           round(alloc["quantity"], 6),
            "quantity_after_fees": round(qty_after_fees, 6),

            # Gas
            "gas_gwei":           gas_check["gas_gwei"],
            "gas_status":         gas_check["status"],

            # Slippage
            "slippage_pct":       slippage.get("slippage_pct"),
            "slippage_status":    slippage["status"],
            "uniswap_tolerance":  slippage.get("uniswap_tolerance", 0.5),

            # Stop-loss / Take-profit
            "stop_loss_price":    levels["stop_loss"],
            "stop_loss_pct":      levels["stop_loss_pct"],
            "tp1_price":          levels["tp1_price"],
            "tp2_price":          levels["tp2_price"],
            "tp3_price":          levels["tp3_price"],
            "risk_reward":        levels["risk_reward_ratio"],

            # Status
            "is_viable":          is_viable,
            "recommendation":     alloc["recommendation"],
            "reason":             alloc["reason"],
        }

        trades.append(trade)
        if is_viable:
            execution_priority += 1

    # Sort: viable trades first, then by composite score
    trades.sort(key=lambda x: (not x["is_viable"], x["execution_priority"]))

    # DCA schedule
    viable_budget = sum(t["gross_usd"] for t in trades if t["is_viable"])
    dca = get_dca_schedule(viable_budget, weeks=4, market_fear_greed=fg_value)

    # Summary
    viable_count    = sum(1 for t in trades if t["is_viable"])
    projected_value = portfolio.get("projected_value", budget_usd)
    projected_roi   = portfolio.get("projected_roi_pct", 0)

    elapsed = round(time.time() - start, 2)

    return {
        "status":           "OK" if viable_count > 0 else "NO_VIABLE_TRADES",
        "roi_target_pct":   roi_target,
        "budget_usd":       budget_usd,
        "viable_trades":    viable_count,
        "total_trades":     len(trades),
        "trades":           trades,
        "total_gas_usd":    round(total_gas_usd, 4),
        "projected_value":  projected_value,
        "projected_roi_pct": projected_roi,
        "hits_roi_target":  projected_roi >= roi_target,
        "dca_schedule":     dca,
        "market_context":   analysis_report.get("market_context", {}),
        "warnings":         warnings,
        "plan_created_at":  datetime.now(timezone.utc).isoformat(),
        "elapsed_s":        elapsed,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# One-Shot Agent Helper
# ═══════════════════════════════════════════════════════════════════════════════

def get_full_trading_plan(roi_target_pct: float = 20.0,
                          budget_usd: float = 1000.0) -> dict:
    """
    Convenience function: analyze + build trade plan in one call.
    This is what the agent calls when user says "I want 20% ROI".

    Returns:
        Combined analysis + trade plan dict
    """
    from trading_analyzer import analyze_all_tokens

    logger.info("[strategy] Building full trading plan: ROI=%.0f%% budget=$%.0f",
                roi_target_pct, budget_usd)

    # Step 1: Analyze all tokens
    analysis = analyze_all_tokens(
        roi_target_pct=roi_target_pct,
        budget_usd=budget_usd,
        top_n=8,
    )

    # Step 2: Build execution plan
    plan = build_trade_plan(analysis, budget_usd)

    # Merge for convenience
    plan["top_picks"]        = analysis["top_picks"]
    plan["tokens_analyzed"]  = analysis["tokens_analyzed"]
    plan["analysis_warnings"] = analysis["warnings"]

    return plan


# ═══════════════════════════════════════════════════════════════════════════════
# Chat Formatter
# ═══════════════════════════════════════════════════════════════════════════════

def format_plan_for_chat(plan: dict) -> str:
    """
    Format a complete trade plan into human-readable chat response.
    This is what the agent sends back to the user.
    """
    roi    = plan.get("roi_target_pct", 20)
    budget = plan.get("budget_usd", 1000)
    ctx    = plan.get("market_context", {})
    fg     = ctx.get("fear_greed_value", 50)
    fg_lbl = ctx.get("fear_greed_label", "UNKNOWN")

    lines = [
        f"## Trading Plan — {roi:.0f}% ROI Target",
        f"**Budget:** ${budget:.0f}  |  "
        f"**Market:** Fear & Greed = {fg}/100 ({fg_lbl})",
        f"",
    ]

    # Warnings
    all_warnings = list(plan.get("warnings", []))
    if all_warnings:
        for w in all_warnings[:3]:
            lines.append(f"⚠️  {w}")
        lines.append("")

    if plan["status"] == "NO_VIABLE_TRADES" or plan["status"] == "NO_TRADES":
        lines.append("❌ **No viable trades under current conditions.**")
        lines.append("")
        lines.append("**What to do instead:**")
        lines.append("• Wait for Fear & Greed Index to rise above 40")
        lines.append("• Use DCA: invest small amounts weekly regardless of market")
        lines.append(f"• Current best RWA option: ONDO (5.2% APY — earns yield even in bear market)")
    else:
        # Viable trades
        lines.append(f"### {plan['viable_trades']} Trade(s) Ready to Execute")
        lines.append("")
        for trade in plan["trades"]:
            if not trade["is_viable"]:
                continue
            status_icon = "✅" if trade["gas_status"] == "OK" else "⚠️"
            lines.append(
                f"**{status_icon} {trade['symbol']}** — "
                f"${trade['gross_usd']:.0f} via {trade['dex']}"
            )
            lines.append(
                f"   Buy: ${trade['entry_price']:.4f} × {trade['quantity']:.4f} tokens"
            )
            lines.append(
                f"   Fees: gas ${trade['gas_usd']:.3f} + DEX ${trade['dex_fee_usd']:.3f} "
                f"= ${trade['total_fees_usd']:.3f} total"
            )
            lines.append(
                f"   Slippage: ~{trade['slippage_pct']:.2f}%  "
                f"(Uniswap tolerance: {trade['uniswap_tolerance']:.1f}%)"
            ) if trade["slippage_pct"] else None
            lines.append(
                f"   Stop-Loss: ${trade['stop_loss_price']:.4f} "
                f"({trade['stop_loss_pct']:.0f}%) | "
                f"TP1: ${trade['tp1_price']:.4f} | "
                f"TP2: ${trade['tp2_price']:.4f}"
            )
            lines.append(
                f"   Risk/Reward: {trade['risk_reward']:.1f}x"
            )
            lines.append("")

        # Summary
        lines.append(
            f"**Projected:** ${plan['projected_value']:.0f} in 12 months "
            f"(+{plan['projected_roi_pct']:.1f}% ROI) "
            f"{'✅' if plan['hits_roi_target'] else '⚠️ below target'}"
        )
        lines.append(
            f"**Gas cost:** ~${plan['total_gas_usd']:.3f} total"
        )
        lines.append("")

    # DCA Schedule
    dca = plan.get("dca_schedule", {})
    if dca:
        lines.append(f"### DCA Schedule ({dca.get('strategy', 'EQUAL_DCA')})")
        lines.append(dca.get("rationale", ""))
        lines.append("")
        for week in dca.get("schedule", []):
            lines.append(
                f"• Week {week['week']} ({week['date']}): "
                f"${week['amount_usd']:.0f} ({week['weight_pct']:.0f}%)"
            )

    return "\n".join(line for line in lines if line is not None)
