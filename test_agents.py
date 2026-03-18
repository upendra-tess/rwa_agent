"""
test_agents.py — Run and inspect all 5 macro agents
Usage: python test_agents.py
"""
import logging
logging.basicConfig(level=logging.INFO)

from agents.macro_analysis import run_macro_analysis

profile = {
    "risk_tolerance": "moderate",
    "investment_horizon": "medium",
    "target_roi_pct": 15.0,
    "budget_usd": 10000,
    "jurisdiction": "US",
}

print("\nRunning all 5 agents in parallel...\n")
r = run_macro_analysis(profile)

print()
print("=" * 55)
print("MACRO ANALYSIS COMPLETE")
print("=" * 55)
print("Overall Score :", r["overall_macro_score"], "/ 100")
print("Agents        :", r["agents_completed"])
print("Recommended   :", r["recommended_asset_types"])

print()
print("--- Agent Status ---")
for k, v in r["sub_agent_status"].items():
    status = v["status"]
    print(f"  {status:8}  {k}")

# ── Industry ─────────────────────────────────────────────
print()
print("--- Industry Analysis ---")
ind = r.get("industry_analysis", {})
print("  Top sectors     :", ind.get("top_sectors"))
print("  Growth outlook  :", ind.get("growth_outlook"))
print("  Protocols       :", ind.get("rwa_protocols_tracked"))
print("  RWA tokens      :", ind.get("rwa_tokens_tracked"))
print("  Data source     :", ind.get("data_source"))
for s in ind.get("recommended_sectors", [])[:3]:
    tvl = s.get("total_tvl_usd", 0)
    print(f"    {s['name']}: score={s['score']} tvl=${tvl/1e6:.0f}M growth={s['avg_change_30d']:.1f}%")

# ── Financial ────────────────────────────────────────────
print()
print("--- Financial Analysis ---")
fin = r.get("financial_analysis", {})
rate_val = fin.get("rate_value", 0)
print(f"  Rate env        : {fin.get('interest_rate_environment')} ({rate_val:.2f}%)")
infl = fin.get("inflation_impact", {})
print(f"  Inflation       : {infl.get('severity')} ({infl.get('current_rate')}%)")
gdp = fin.get("gdp_assessment", {})
print(f"  GDP             : {gdp.get('outlook')} ({gdp.get('growth_rate')}%)")
print(f"  Duration rec    : {fin.get('recommended_duration')}")
print(f"  Score           : {fin.get('financial_environment_score')}")
print(f"  Data source     : {fin.get('data_source')}")
for imp in fin.get("investment_implications", []):
    print(f"    - {imp}")

# ── Cash Flow ────────────────────────────────────────────
print()
print("--- Cash Flow Analysis ---")
cf = r.get("cash_flow_analysis", {})
inc = cf.get("projected_annual_income", {})
print(f"  Min yield req   : {cf.get('preferred_yield_min_pct')}%")
print(f"  Effective yield : {inc.get('effective_yield_pct')}%")
print(f"  Annual income   : ${inc.get('total_annual_usd')}")
print(f"  Monthly income  : ${inc.get('total_monthly_usd')}")
print(f"  Stability       : {cf.get('cash_flow_stability_rating')}")
print(f"  Pools analyzed  : {cf.get('total_pools_analyzed')}")
print(f"  Data source     : {cf.get('data_source')}")
for p in cf.get("top_yield_pools", [])[:5]:
    tvl = p.get("tvl_usd", 0)
    print(f"    {p['project']} ({p['symbol']}): APY={p['apy']}% TVL=${tvl/1e6:.0f}M")

# ── Geopolitical ─────────────────────────────────────────
print()
print("--- Geopolitical Analysis ---")
geo = r.get("geopolitical_analysis", {})
print(f"  Risk level      : {geo.get('geopolitical_risk_level')}")
print(f"  Safe juris.     : {geo.get('safe_jurisdictions')}")
print(f"  Avg clarity     : {geo.get('regulatory_clarity_avg_score')}")
print(f"  GDELT RWA news  : {geo.get('gdelt_rwa_articles')} articles")
print(f"  GDELT sanctions : {geo.get('gdelt_sanctions_articles')} articles")
print(f"  Data source     : {geo.get('data_source')}")
for h in geo.get("gdelt_top_headlines", [])[:3]:
    print(f"    - {h}")
for j in geo.get("ranked_jurisdictions", [])[:5]:
    print(f"    {j['id']}: score={j['score']} clarity={j['regulatory_clarity']} stance={j['crypto_stance']}")

# ── Market ───────────────────────────────────────────────
print()
print("--- Market Analysis ---")
mkt = r.get("market_analysis", {})
reg = mkt.get("market_regime", {})
fg = mkt.get("fear_greed", {})
rwa_mom = mkt.get("rwa_sector_momentum", {})
vol = mkt.get("volatility_summary", {})
print(f"  Regime          : {reg.get('regime')} — {reg.get('description')}")
print(f"  Fear & Greed    : {fg.get('value')} ({fg.get('label')}) trend={fg.get('trend')}")
print(f"  RWA momentum    : {rwa_mom.get('avg_momentum')} ({rwa_mom.get('trend')})")
print(f"  Volatility      : {vol.get('volatility_regime')}")
print(f"  Momentum bias   : {mkt.get('momentum_bias')}")
print(f"  GDELT articles  : {mkt.get('gdelt_news', {}).get('count')}")
print(f"  Reddit posts    : {mkt.get('reddit', {}).get('count')}")
print(f"  GT pools        : {len(mkt.get('gecko_terminal_pools', []))}")
print(f"  Data source     : {mkt.get('data_source')}")
print("  Top gainers:")
for g in mkt.get("top_gainers", [])[:3]:
    c = g.get("changes", {})
    print(f"    {g['symbol']:10} momentum={g['momentum_score']:+.1f}  30d={c.get('30d',0):+.1f}%  7d={c.get('7d',0):+.1f}%")

# ── Summary ──────────────────────────────────────────────
print()
print("=" * 55)
print("SUMMARY")
print("=" * 55)
print(r.get("summary", ""))
