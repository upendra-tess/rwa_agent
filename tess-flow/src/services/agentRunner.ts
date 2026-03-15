import { AgentRun, AgentIconName, RunStatus } from "../types";
import { AGENT_CATALOG } from "../data/catalog";

// ─── Mock run engine ──────────────────────────────────────────────────────────
// Replace with real API calls when the backend is ready.

const STEP_TEMPLATES: Record<string, string[]> = {
  "research-analyst":  ["Parsing query", "Searching the web", "Reading sources", "Extracting key facts", "Synthesising report", "Formatting output"],
  "code-reviewer":     ["Parsing code", "Running static analysis", "Checking security patterns", "Evaluating performance", "Generating inline comments", "Compiling report"],
  "payment-ops":       ["Authenticating payment rails", "Fetching transactions", "Running reconciliation", "Flagging anomalies", "Generating audit report"],
  "data-analyst":      ["Loading dataset", "Cleaning data", "Running statistical analysis", "Detecting anomalies", "Building summary", "Formatting output"],
  "email-composer":    ["Parsing intent", "Drafting subject line", "Composing body", "Applying tone", "Finalising email"],
  "scheduler":         ["Reading calendar", "Finding available slots", "Resolving conflicts", "Drafting invite", "Sending confirmation"],
  "security-auditor":  ["Fetching target", "Running static analysis", "Checking known CVEs", "Classifying findings", "Generating risk report"],
  "portfolio-tracker": ["Fetching on-chain data", "Aggregating balances", "Computing P&L", "Generating rebalancing plan", "Building report"],
  "seo-optimizer":     ["Crawling page", "Analysing metadata", "Checking keywords", "Evaluating backlinks", "Generating recommendations"],
  "social-writer":     ["Parsing topic", "Researching context", "Drafting X post", "Drafting LinkedIn post", "Drafting Instagram caption", "Generating hashtags"],
};

const DEFAULT_STEPS = ["Initialising", "Processing", "Generating output", "Finalising"];

const MOCK_OUTPUTS: Record<string, string> = {
  "research-analyst": `## Research Report\n\n**Summary:** Based on 12 sources, the topic has seen significant growth in Q1 2026.\n\n### Key Findings\n1. Market adoption increased by 38% YoY.\n2. Three dominant frameworks emerged: A, B, and C.\n3. Regulatory clarity in the EU accelerated enterprise adoption.\n\n### Sources\n- Source A (relevance: 96%)\n- Source B (relevance: 91%)\n- Source C (relevance: 87%)`,
  "code-reviewer": `## Code Review Report\n\n**Overall Score:** 82/100\n\n### Issues Found\n\n**High Severity (1)**\n- Line 42: Potential reentrancy vulnerability in \`withdraw()\`.\n\n**Medium Severity (2)**\n- Line 18: Magic number \`1000\` — extract to named constant.\n- Line 77: Missing input validation on \`amount\` parameter.\n\n**Low Severity (3)**\n- Unused import on line 5.\n- Inconsistent naming convention.\n- Missing JSDoc on public functions.\n\n### Recommendation\nAddress the reentrancy issue before deployment.`,
  "payment-ops": `## Payment Reconciliation Report\n\n**Period:** Last 7 days\n**Total transactions:** 1,284\n**Reconciled:** 1,279 (99.6%)\n\n### Anomalies Detected\n- 3 duplicate invoices flagged (IDs: #4421, #4422, #4423)\n- 2 transactions with mismatched currency codes\n\n### Action Required\nReview flagged invoices and confirm currency corrections.`,
  "data-analyst": `## Data Analysis Summary\n\n**Dataset:** 36 months of sales data\n**Rows processed:** 108,432\n\n### Key Insights\n- **Seasonality:** Sales peak in Q4 (+42% vs average).\n- **Trend:** 12-month rolling average shows 8.3% CAGR.\n- **Anomaly:** March 2025 shows an unexplained 22% dip.\n\n### Recommended Actions\n1. Stock up inventory by end of September.\n2. Investigate the March 2025 anomaly.`,
  "email-composer": `**Subject:** Following up on our product demo\n\nHi [Name],\n\nThank you for taking the time to explore our platform during yesterday's demo.\n\nAs discussed, here are the next steps:\n- We'll send over the pricing proposal by end of week.\n- Our team is available for a technical deep-dive whenever suits you.\n\nBest regards,\n[Your Name]`,
  "scheduler": `**Meeting Scheduled ✓**\n\nTitle: Sync with team\nDate: Wednesday, 12 March 2026\nTime: 2:00 PM – 2:30 PM UTC\nAttendees: alice@example.com, bob@example.com\n\nCalendar invites sent. A reminder will be sent 15 minutes before.`,
  "security-auditor": `## Security Audit Report\n\n**Target:** 0x1234...abcd\n**Severity breakdown:** 1 Critical · 2 High · 4 Medium · 6 Low\n\n### Critical\n- **Unchecked external call** in \`execute()\` — attacker can drain funds.\n\n### High\n- **Integer overflow** in \`calculateReward()\` (Solidity <0.8).\n- **Missing access control** on \`setOwner()\`.\n\n### Recommendation\nDo not deploy until Critical and High findings are resolved.`,
  "portfolio-tracker": `## Portfolio Summary\n\n**Total Value:** $521,990\n**24h Change:** +1.9% (+$9,800)\n\n| Asset | Balance | Value     | Allocation |\n|-------|---------|-----------|------------|\n| USDC  | 184,200 | $184,200  | 35%        |\n| ETH   | 52.42   | $158,050  | 30%        |\n| SOL   | 890     | $94,340   | 18%        |\n| BTC   | 0.93    | $85,400   | 17%        |\n\n### Rebalancing Recommendation\nCurrent allocation is within strategy bounds. No action required.`,
  "seo-optimizer": `## SEO Audit Report\n\n**Page:** https://example.com/page\n**Score:** 74/100\n\n### Quick Wins\n1. Add meta description (missing).\n2. Compress hero image — 1.4 MB, target < 200 KB.\n3. Add alt text to 3 images.\n\n### Keyword Analysis\n- Target keyword density: 0.8% (target 1–2%).\n- Title tag missing target keyword.\n\n### Recommendations\nAddress quick wins first — estimated +12 point score improvement.`,
  "social-writer": `**X (Twitter)**\n🚀 Excited to share our latest update! [Topic] is changing the way teams work. Here's what you need to know 👇\n#AI #Productivity #Innovation\n\n---\n**LinkedIn**\nWe're thrilled to announce [Topic]. After months of development, this is a milestone moment for our team.\n\nHere's why this matters: [Key insight]\n\nRead more → [link]\n\n---\n**Instagram**\nBig news! ✨ [Topic] is here. Tap the link in bio to learn more. 🔗\n#NewRelease #Tech #Growth`,
};

export function startRun(
  agentId: string,
  inputs: Record<string, string>,
  onStep: (run: AgentRun) => void,
  onComplete: (run: AgentRun) => void
): AgentRun {
  const agent = AGENT_CATALOG.find((a) => a.id === agentId);
  const stepLabels = STEP_TEMPLATES[agentId] ?? DEFAULT_STEPS;
  const steps = stepLabels.map((label, i) => ({
    id: `step-${i}`,
    label,
    status: "pending" as const,
  }));

  const run: AgentRun = {
    id: `run-${Date.now()}`,
    agentId,
    agentName: agent?.name ?? agentId,
    agentIconName: (agent?.iconName ?? "FlaskConical") as AgentIconName,
    status: "running",
    inputs,
    steps: steps.map((s) => ({ ...s })),
    output: "",
    startedAt: new Date().toISOString(),
    tokenCount: 0,
  };

  let stepIndex = 0;

  const advanceStep = () => {
    if (stepIndex >= steps.length) {
      const finalRun: AgentRun = {
        ...run,
        status: "success" as RunStatus,
        output: MOCK_OUTPUTS[agentId] ?? "Task completed successfully.",
        finishedAt: new Date().toISOString(),
        durationMs: Date.now() - new Date(run.startedAt).getTime(),
        tokenCount: Math.floor(Math.random() * 2000) + 500,
        steps: run.steps.map((s) => ({ ...s, status: "done" as const })),
      };
      Object.assign(run, finalRun);
      onComplete({ ...run });
      return;
    }

    run.steps[stepIndex] = {
      ...run.steps[stepIndex],
      status: "running",
      startedAt: new Date().toISOString(),
    };
    onStep({ ...run, steps: run.steps.map((s) => ({ ...s })) });

    setTimeout(() => {
      run.steps[stepIndex] = {
        ...run.steps[stepIndex],
        status: "done",
        finishedAt: new Date().toISOString(),
        output: `${run.steps[stepIndex].label} complete`,
      };
      stepIndex++;
      onStep({ ...run, steps: run.steps.map((s) => ({ ...s })) });
      advanceStep();
    }, 600 + Math.random() * 900);
  };

  setTimeout(advanceStep, 300);
  return run;
}
