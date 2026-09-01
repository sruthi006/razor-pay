// Centralized API client. All backend URLs live here — never in components.
// Point the frontend at the FastAPI service with VITE_API_BASE_URL.

import {
  mockAudit,
  mockBreakdown,
  mockBusinessImpact,
  mockConfidence,
  mockDashboard,
  mockPredict,
  mockRetryDistribution,
  mockSimulate,
  mockTransactionsResponse,
} from "./mock";
import type {
  AuditResponse,
  BusinessImpactResponse,
  ConfidenceResponse,
  DatasetValidationResult,
  DashboardResponse,
  InferenceResponse,
  PredictResponse,
  RecoveryBreakdownResponse,
  RetryDistributionResponse,
  SimulateResponse,
  TransactionContext,
  TransactionsResponse,
} from "./types";

export const API_BASE_URL: string =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined)?.replace(/\/$/, "") ?? "";

const USE_MOCK_DATA_FLAG =
  import.meta.env["VITE_USE_MOCK_DATA"] === true ||
  import.meta.env["VITE_USE_MOCK_DATA"] === "true" ||
  import.meta.env["VITE_USE_MOCK_DATA"] === "1";

export const USING_MOCK_DATA = USE_MOCK_DATA_FLAG;

export const ENDPOINTS = {
  dashboard: "/api/dashboard",
  businessImpact: "/api/business-impact",
  recoveryBreakdown: "/api/recovery-breakdown",
  retryDistribution: "/api/retry-distribution",
  confidence: "/api/confidence",
  audit: "/api/audit",
  transactions: "/api/transactions",
  predict: "/api/predict",
  simulate: "/api/simulate",
} as const;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function normalizePaymentMethod(value: string | undefined): string {
  const method = (value ?? "").trim();
  if (method === "Netbanking") return "Net Banking";
  return method || "Credit Card";
}

function normalizeConfidenceTier(value: string | undefined): "Low" | "Medium" | "High" {
  const tier = (value ?? "").toLowerCase();
  if (tier === "medium") return "Medium";
  if (tier === "high") return "High";
  return "Low";
}

function transactionToPredictionRequest(ctx: TransactionContext) {
  const failedAt = new Date(ctx.failed_at ?? new Date().toISOString());
  const priorFailures = Number(ctx.customer_prior_failures ?? 0);
  const priorRecoveries = Number(ctx.customer_prior_recoveries ?? 0);
  const successRate =
    priorFailures + priorRecoveries > 0
      ? Math.min(1, Math.max(0, priorRecoveries / (priorFailures + priorRecoveries)))
      : 0.5;

  return {
    amount_inr: Number(ctx.amount_inr ?? 0),
    decline_reason: String(ctx.decline_reason ?? ""),
    payment_method: normalizePaymentMethod(ctx.payment_method),
    hour_of_day: Number.isNaN(failedAt.getHours()) ? 12 : failedAt.getHours(),
    day_of_month: Number.isNaN(failedAt.getDate()) ? 1 : failedAt.getDate(),
    day_of_week: Number.isNaN(failedAt.getDay()) ? 1 : failedAt.getDay(),
    customer_previous_success_rate: successRate,
    customer_previous_failure_count: priorFailures,
    days_since_last_successful_payment: Number(ctx.customer_tenure_days ?? 0) / 30,
  };
}

async function request<T>(
  path: string,
  fallback: () => T | Promise<T>,
  init?: RequestInit,
): Promise<T> {
  if (USING_MOCK_DATA) {
    await new Promise((r) => setTimeout(r, 260));
    return fallback();
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!res.ok) {
    throw new ApiError(`Request to ${path} failed (${res.status})`, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  getDashboard: () => request<DashboardResponse>(ENDPOINTS.dashboard, () => mockDashboard),
  getBusinessImpact: () =>
    request<BusinessImpactResponse>(ENDPOINTS.businessImpact, () => mockBusinessImpact),
  getRecoveryBreakdown: (dimension: string) =>
    request<RecoveryBreakdownResponse>(
      `${ENDPOINTS.recoveryBreakdown}?dimension=${encodeURIComponent(dimension)}`,
      () => mockBreakdown,
    ),
  getRetryDistribution: () =>
    request<RetryDistributionResponse>(ENDPOINTS.retryDistribution, () => mockRetryDistribution),
  getConfidence: () => request<ConfidenceResponse>(ENDPOINTS.confidence, () => mockConfidence),
  getAudit: (transactionId: string) =>
    request<AuditResponse>(
      `${ENDPOINTS.audit}?transaction_id=${encodeURIComponent(transactionId)}`,
      () => mockAudit,
    ),
  getTransactions: (page = 1, pageSize = 25) =>
    request<TransactionsResponse>(`/api/transactions?page=${page}&page_size=${pageSize}`, () => mockTransactionsResponse),
  predict: (ctx: TransactionContext) =>
    request<PredictResponse>(ENDPOINTS.predict, () => mockPredict(ctx), {
      method: "POST",
      body: JSON.stringify(transactionToPredictionRequest(ctx)),
    }),
  simulate: (ctx: TransactionContext) =>
    request<SimulateResponse>(ENDPOINTS.simulate, () => mockSimulate(ctx, mockPredict(ctx)), {
      method: "POST",
      body: JSON.stringify({
        ...transactionToPredictionRequest(ctx),
        transaction_id: ctx.transaction_id ?? `txn-${Date.now()}`,
      }),
    }),
  // Inference endpoints
  validateCsv: async (file: File): Promise<DatasetValidationResult> => {
    if (USING_MOCK_DATA) {
      return {
        valid: true,
        record_count: 1000,
        errors: [],
        warnings: [],
      };
    }
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/api/inference/validate-csv`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      throw new ApiError(`CSV validation failed (${res.status})`, res.status);
    }
    return (await res.json()) as DatasetValidationResult;
  },
  uploadAndInfer: async (file: File): Promise<InferenceResponse> => {
    if (USING_MOCK_DATA) {
      return {
        dataset_source: "upload",
        total_records: 1000,
        eligible_records: 850,
        processed_records: 850,
        failed_records: 0,
        eligible_by_confidence: { High: 340, Medium: 425, Low: 85 },
        avg_selected_retry_hours: 12.5,
        results: [],
        errors: [],
      };
    }
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/api/inference/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const error = await res.text();
      throw new ApiError(`Upload failed (${res.status}): ${error}`, res.status);
    }
    return (await res.json()) as InferenceResponse;
  },
  loadDemoDataset: async (): Promise<InferenceResponse> => {
    if (USING_MOCK_DATA) {
      return {
        dataset_source: "demo",
        total_records: 100000,
        eligible_records: 85000,
        processed_records: 85000,
        failed_records: 0,
        eligible_by_confidence: { High: 34000, Medium: 42500, Low: 8500 },
        avg_selected_retry_hours: 12.5,
        results: [],
        errors: [],
      };
    }
    return request<InferenceResponse>("/api/inference/demo", async () => ({
      dataset_source: "demo",
      total_records: 0,
      eligible_records: 0,
      processed_records: 0,
      failed_records: 0,
      eligible_by_confidence: {},
      results: [],
      errors: ["Demo endpoint unavailable"],
    }));
  },
};

export function normalizeConfidenceRecord(record: {
  smart_retry_confidence?: string;
  eligible_transactions?: number;
  baseline_recovered_inr?: number;
  smart_retry_recovered_inr?: number;
  incremental_inr?: number;
}): {
  tier: "high" | "medium" | "low";
  label: string;
  transactions: number;
  fixed_schedule_inr: number;
  smart_retry_inr: number;
  incremental_inr: number;
} {
  const tier = normalizeConfidenceTier(record.smart_retry_confidence).toLowerCase() as
    | "high"
    | "medium"
    | "low";
  return {
    tier,
    label: `${normalizeConfidenceTier(record.smart_retry_confidence)} confidence`,
    transactions: Number(record.eligible_transactions ?? 0),
    fixed_schedule_inr: Number(record.baseline_recovered_inr ?? 0),
    smart_retry_inr: Number(record.smart_retry_recovered_inr ?? 0),
    incremental_inr: Number(record.incremental_inr ?? 0),
  };
}

export function normalizeBreakdownRows(data: RecoveryBreakdownResponse | undefined) {
  if (!data?.items) return [];
  return data.items.map((item) => {
    const key = String(
      item.decline_reason ?? item.payment_method ?? item.amount_band ?? item.key ?? "",
    );
    const valueMap = item as Record<string, string | number | boolean | null>;
    const label = key
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
    return {
      key,
      label,
      fixed_schedule_inr: Number(valueMap.baseline_recovered_inr ?? valueMap.fixed_schedule_inr ?? 0),
      smart_retry_inr: Number(valueMap.smart_retry_recovered_inr ?? valueMap.smart_retry_inr ?? 0),
      fixed_schedule_rate_pct: Number(valueMap.baseline_recovery_rate ?? valueMap.fixed_schedule_rate_pct ?? 0) * 100,
      smart_retry_rate_pct: Number(valueMap.smart_retry_recovery_rate ?? valueMap.smart_retry_rate_pct ?? 0) * 100,
    };
  });
}

export function normalizeRetryDistribution(data: RetryDistributionResponse | undefined) {
  if (!data?.distribution) return [];
  return data.distribution.map((item) => ({
    offset_label: `${item.selected_retry_hours}h`,
    offset_minutes: Math.round(Number(item.selected_retry_hours) * 60),
    selected_count: Number(item.eligible_transactions ?? 0),
    recovery_rate_pct: Number(item.smart_retry_recovery_rate ?? 0) * 100,
  }));
}
