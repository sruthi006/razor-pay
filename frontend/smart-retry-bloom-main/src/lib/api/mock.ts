// ---------------------------------------------------------------------------
// MOCK SERVICE LAYER
// Realistic synthetic-simulation data used only while the FastAPI backend is
// unavailable. Nothing here is live payment data. Delete this file once
// VITE_API_BASE_URL points at a running backend.
// ---------------------------------------------------------------------------

import type {
  AuditResponse,
  BusinessImpactResponse,
  ConfidenceResponse,
  DashboardResponse,
  PredictResponse,
  RecoveryBreakdownResponse,
  RetryDistributionResponse,
  SimulateResponse,
  TransactionContext,
  TransactionsResponse,
} from "./types";

const FIXED = 16_930_000;
const SMART = 24_020_000;
const INCREMENTAL = SMART - FIXED;
const LIFT = 41.87;

export const mockDashboard: DashboardResponse = {
  currency: "INR",
  simulation: true,
  kpis: {
    total_failed_payments: 48_260,
    eligible_for_recovery: 39_884,
    fixed_schedule_recovered_inr: FIXED,
    smart_retry_recovered_inr: SMART,
    incremental_revenue_inr: INCREMENTAL,
    recovery_lift_pct: LIFT,
  },
  strategies: [
    {
      strategy: "fixed_schedule",
      label: "Fixed Schedule",
      recovered_inr: FIXED,
      recovery_rate_pct: 31.4,
      recovered_transactions: 12_524,
    },
    {
      strategy: "smart_retry",
      label: "Smart Retry",
      recovered_inr: SMART,
      recovery_rate_pct: 43.6,
      recovered_transactions: 17_389,
    },
  ],
};

export const mockBusinessImpact: BusinessImpactResponse = {
  fixed_schedule_inr: FIXED,
  smart_retry_inr: SMART,
  incremental_inr: INCREMENTAL,
  lift_pct: LIFT,
  fixed_schedule_rate_pct: 31.4,
  smart_retry_rate_pct: 43.6,
  methodology_note:
    "Results are from a synthetic-data policy simulation and are not production payment performance.",
};

export const mockBreakdown: RecoveryBreakdownResponse = {
  by_decline_reason: [
    { key: "insufficient_funds", label: "Insufficient Funds", fixed_schedule_inr: 5_120_000, smart_retry_inr: 8_460_000, fixed_schedule_rate_pct: 27.8, smart_retry_rate_pct: 45.1 },
    { key: "issuer_declined", label: "Issuer Declined", fixed_schedule_inr: 3_640_000, smart_retry_inr: 5_020_000, fixed_schedule_rate_pct: 29.6, smart_retry_rate_pct: 40.2 },
    { key: "network_timeout", label: "Network Timeout", fixed_schedule_inr: 2_980_000, smart_retry_inr: 4_310_000, fixed_schedule_rate_pct: 38.4, smart_retry_rate_pct: 52.6 },
    { key: "risk_hold", label: "Risk Hold", fixed_schedule_inr: 2_410_000, smart_retry_inr: 3_180_000, fixed_schedule_rate_pct: 24.1, smart_retry_rate_pct: 31.8 },
    { key: "expired_instrument", label: "Expired Instrument", fixed_schedule_inr: 1_580_000, smart_retry_inr: 1_920_000, fixed_schedule_rate_pct: 14.2, smart_retry_rate_pct: 17.4 },
    { key: "authentication_failed", label: "Authentication Failed", fixed_schedule_inr: 1_200_000, smart_retry_inr: 1_130_000, fixed_schedule_rate_pct: 18.9, smart_retry_rate_pct: 18.1 },
  ],
  by_payment_method: [
    { key: "upi", label: "UPI", fixed_schedule_inr: 5_890_000, smart_retry_inr: 8_920_000, fixed_schedule_rate_pct: 34.2, smart_retry_rate_pct: 49.8 },
    { key: "credit_card", label: "Credit Card", fixed_schedule_inr: 4_620_000, smart_retry_inr: 6_410_000, fixed_schedule_rate_pct: 30.8, smart_retry_rate_pct: 42.3 },
    { key: "debit_card", label: "Debit Card", fixed_schedule_inr: 3_310_000, smart_retry_inr: 4_580_000, fixed_schedule_rate_pct: 28.6, smart_retry_rate_pct: 39.5 },
    { key: "netbanking", label: "Netbanking", fixed_schedule_inr: 2_040_000, smart_retry_inr: 2_920_000, fixed_schedule_rate_pct: 26.4, smart_retry_rate_pct: 36.7 },
    { key: "wallet", label: "Wallet", fixed_schedule_inr: 1_070_000, smart_retry_inr: 1_190_000, fixed_schedule_rate_pct: 31.1, smart_retry_rate_pct: 34.0 },
  ],
  by_amount_band: [
    { key: "0_500", label: "₹0 – ₹500", fixed_schedule_inr: 980_000, smart_retry_inr: 1_240_000, fixed_schedule_rate_pct: 36.4, smart_retry_rate_pct: 45.9 },
    { key: "500_2k", label: "₹500 – ₹2K", fixed_schedule_inr: 2_640_000, smart_retry_inr: 3_780_000, fixed_schedule_rate_pct: 34.1, smart_retry_rate_pct: 46.8 },
    { key: "2k_10k", label: "₹2K – ₹10K", fixed_schedule_inr: 5_320_000, smart_retry_inr: 7_910_000, fixed_schedule_rate_pct: 32.5, smart_retry_rate_pct: 45.2 },
    { key: "10k_50k", label: "₹10K – ₹50K", fixed_schedule_inr: 5_180_000, smart_retry_inr: 7_460_000, fixed_schedule_rate_pct: 29.8, smart_retry_rate_pct: 41.6 },
    { key: "50k_plus", label: "₹50K+", fixed_schedule_inr: 2_810_000, smart_retry_inr: 3_630_000, fixed_schedule_rate_pct: 24.7, smart_retry_rate_pct: 33.1 },
  ],
};

export const mockRetryDistribution: RetryDistributionResponse = {
  buckets: [
    { offset_label: "15m", offset_minutes: 15, selected_count: 1_820, recovery_rate_pct: 31.2 },
    { offset_label: "30m", offset_minutes: 30, selected_count: 2_460, recovery_rate_pct: 34.8 },
    { offset_label: "1h", offset_minutes: 60, selected_count: 4_910, recovery_rate_pct: 40.1 },
    { offset_label: "2h", offset_minutes: 120, selected_count: 8_240, recovery_rate_pct: 48.6 },
    { offset_label: "6h", offset_minutes: 360, selected_count: 6_780, recovery_rate_pct: 46.2 },
    { offset_label: "12h", offset_minutes: 720, selected_count: 5_120, recovery_rate_pct: 43.7 },
    { offset_label: "24h", offset_minutes: 1440, selected_count: 6_340, recovery_rate_pct: 45.4 },
    { offset_label: "48h", offset_minutes: 2880, selected_count: 2_640, recovery_rate_pct: 36.9 },
    { offset_label: "72h", offset_minutes: 4320, selected_count: 1_574, recovery_rate_pct: 29.5 },
  ],
};

export const mockConfidence: ConfidenceResponse = {
  insight: "Low-confidence recommendations should be bounded or stopped.",
  tiers: [
    { tier: "high", label: "High", transactions: 18_420, fixed_schedule_inr: 8_940_000, smart_retry_inr: 16_940_000, incremental_inr: 8_000_000 },
    { tier: "medium", label: "Medium", transactions: 13_180, fixed_schedule_inr: 5_120_000, smart_retry_inr: 6_770_000, incremental_inr: 1_650_000 },
    { tier: "low", label: "Low", transactions: 8_284, fixed_schedule_inr: 2_870_000, smart_retry_inr: 310_000, incremental_inr: -2_560_000 },
  ],
};

const DECLINE_REASONS = [
  "Insufficient Funds",
  "Issuer Declined",
  "Network Timeout",
  "Risk Hold",
  "Expired Instrument",
  "Authentication Failed",
];
const METHODS = ["UPI", "Credit Card", "Debit Card", "Netbanking", "Wallet"];

function seeded(n: number) {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

export const mockTransactions: TransactionContext[] = Array.from({ length: 14 }, (_, i) => {
  const r = seeded(i + 1);
  const base = new Date("2026-08-26T09:00:00Z").getTime();
  return {
    transaction_id: `TXN-${(48210 + i * 37).toString()}`,
    amount_inr: Math.round((400 + r * 46_000) / 10) * 10,
    decline_reason: DECLINE_REASONS[i % DECLINE_REASONS.length]!,
    payment_method: METHODS[(i * 3) % METHODS.length]!,
    failed_at: new Date(base - i * 47 * 60_000).toISOString(),
    customer_prior_failures: Math.floor(r * 5),
    customer_prior_recoveries: Math.floor(seeded(i + 50) * 4),
    customer_tenure_days: 30 + Math.floor(seeded(i + 90) * 900),
  };
});

export const mockTransactionsResponse: TransactionsResponse = {
  transactions: mockTransactions,
};

const OFFSETS: Array<[string, number]> = [
  ["15m", 15],
  ["30m", 30],
  ["1h", 60],
  ["2h", 120],
  ["6h", 360],
  ["12h", 720],
  ["24h", 1440],
  ["48h", 2880],
  ["72h", 4320],
];

export function mockPredict(ctx: TransactionContext): PredictResponse {
  const seedBase = ctx.transaction_id
    .split("")
    .reduce((acc, c) => acc + c.charCodeAt(0), 0);

  const candidates = OFFSETS.map(([label, minutes], i) => {
    const shape = Math.exp(-Math.pow(Math.log(minutes / 150), 2) / 1.9);
    const noise = seeded(seedBase + i) * 0.12;
    const penalty = ctx.decline_reason === "Expired Instrument" ? 0.45 : 1;
    return {
      offset_label: label,
      offset_minutes: minutes,
      probability: Math.min(0.94, Math.max(0.04, (shape * 0.68 + noise) * penalty)),
    };
  });

  const best = candidates.reduce((a, b) => (b.probability > a.probability ? b : a));
  const eligible =
    ctx.decline_reason !== "Expired Instrument" && ctx.customer_prior_failures < 5;
  const p = best.probability;
  const tier = p >= 0.6 ? "high" : p >= 0.35 ? "medium" : "low";

  return {
    transaction_id: ctx.transaction_id,
    eligible,
    eligibility_reason: eligible
      ? "Within retry budget, instrument is valid and no risk block applies."
      : "Instrument or retry budget makes this payment ineligible for automated retry.",
    recommended_offset_label: best.offset_label,
    recommended_offset_minutes: best.offset_minutes,
    calibrated_probability: p,
    confidence_tier: tier,
    context_summary: `${ctx.decline_reason} on ${ctx.payment_method}. Customer has ${ctx.customer_prior_recoveries} prior recoveries across ${ctx.customer_prior_failures} prior failures over ${ctx.customer_tenure_days} days of tenure.`,
    candidates,
  };
}

export function mockSimulate(ctx: TransactionContext, prediction: PredictResponse): SimulateResponse {
  const recovered =
    prediction.eligible && prediction.confidence_tier !== "low"
      ? prediction.calibrated_probability > 0.4
      : false;
  return {
    transaction_id: ctx.transaction_id,
    executed_at: new Date().toISOString(),
    simulated: true,
    result: recovered ? "recovered" : "stopped",
    recovered_amount_inr: recovered ? ctx.amount_inr : 0,
    message: recovered
      ? `Simulated retry at ${prediction.recommended_offset_label} recovered the payment.`
      : "Simulated workflow stopped — bounded policy prevented a low-value retry.",
  };
}

const STEPS = [
  "Payment Failed",
  "Retry Eligibility Checked",
  "Candidate Retry Times Scored",
  "AI Recommendation Generated",
  "Confidence Evaluated",
  "Bounded Retry Action",
];

export const mockAudit: AuditResponse = {
  records: Array.from({ length: 22 }, (_, i) => {
    const r = seeded(i + 7);
    const tier = r > 0.62 ? "high" : r > 0.3 ? "medium" : "low";
    const result = tier === "low" ? (r > 0.18 ? "stopped" : "failed") : r > 0.42 ? "recovered" : "stopped";
    const amount = Math.round((600 + r * 42_000) / 10) * 10;
    const offset = OFFSETS[Math.floor(r * OFFSETS.length)]![0];
    const base = new Date("2026-08-26T13:40:00Z").getTime() - i * 26 * 60_000;
    return {
      id: `EVT-${9100 + i}`,
      transaction_id: `TXN-${48210 + (i % 14) * 37}`,
      timestamp: new Date(base).toISOString(),
      decline_reason: DECLINE_REASONS[i % DECLINE_REASONS.length]!,
      selected_offset_label: offset,
      confidence_tier: tier as "high" | "medium" | "low",
      result: result as "recovered" | "stopped" | "failed",
      recovered_amount_inr: result === "recovered" ? amount : 0,
      events: [
        ...STEPS.map((step, s) => ({
          step,
          timestamp: new Date(base + s * 90_000).toISOString(),
          detail:
            s === 1
              ? "Eligible — within bounded retry budget"
              : s === 2
                ? "9 candidate retry offsets scored"
                : s === 3
                  ? `Recommended retry in ${offset}`
                  : s === 4
                    ? `${tier} confidence tier`
                    : s === 5
                      ? "Single bounded simulated retry attempt"
                      : "Payment failed at gateway (simulated)",
        })),
        {
          step: result === "recovered" ? "Payment Recovered" : "Workflow Stopped",
          timestamp: new Date(base + 6 * 90_000).toISOString(),
          detail:
            result === "recovered"
              ? "Simulated recovery completed"
              : "Bounded policy stopped further retries",
        },
      ],
    };
  }),
};
