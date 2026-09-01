// Shared API contract types. These match the actual FastAPI responses.
// UI-specific normalizers remain available for chart rendering when needed.

export type ConfidenceTier = "high" | "medium" | "low" | "High" | "Medium" | "Low";
export type RetryResult = "recovered" | "stopped" | "pending" | "failed" | "lost";

export interface DashboardResponse {
  total_failed_transactions: number;
  eligible_transactions: number;
  fixed_recovery_transactions: number;
  smart_recovery_transactions: number;
  fixed_recovery_rate: number;
  smart_recovery_rate: number;
  fixed_recovered_inr: number;
  smart_recovered_inr: number;
  incremental_recovered_inr: number;
  incremental_recovery_rate: number;
  recovered_value_lift_percent: number;
  dataset_source?: string;
  outcome_data_available?: boolean;
  outcome_unavailable_message?: string | null;
}

export interface BusinessImpactResponse {
  fixed_schedule: Record<string, number | string | boolean | null>;
  smart_retry: Record<string, number | string | boolean | null>;
  incremental: Record<string, number | string | boolean | null>;
  bootstrap: Record<string, unknown>;
  limitations: string[];
  outcome_data_available?: boolean;
  outcome_unavailable_message?: string | null;
}

export interface RecoveryBreakdownResponse {
  dimension: string;
  items: Array<Record<string, number | string | boolean | null>>;
}

export interface BreakdownRow {
  key: string;
  label: string;
  fixed_schedule_inr: number;
  smart_retry_inr: number;
  fixed_schedule_rate_pct: number;
  smart_retry_rate_pct: number;
}

export interface RetryDistributionItem {
  selected_retry_hours: number;
  eligible_transactions: number;
  baseline_recovered_transactions: number;
  smart_retry_recovered_transactions: number;
  baseline_recovered_inr: number;
  smart_retry_recovered_inr: number;
  incremental_inr: number;
  baseline_recovery_rate: number;
  smart_retry_recovery_rate: number;
  selection_type: string;
  selection_pct: number;
}

export interface RetryDistributionResponse {
  distribution: RetryDistributionItem[];
  pct_recommendations_at_24_48_72: number;
  pct_recommendations_outside_24_48_72: number;
  recovery_rate_inside_fixed_schedule_times: number;
  recovery_rate_outside_fixed_schedule_times: number;
}

export interface RetryDistributionBucket {
  offset_label: string;
  offset_minutes: number;
  selected_count: number;
  recovery_rate_pct: number;
}

export interface ConfidenceTierStats {
  smart_retry_confidence: "High" | "Medium" | "Low";
  eligible_transactions: number;
  baseline_recovered_transactions: number;
  smart_retry_recovered_transactions: number;
  baseline_recovered_inr: number;
  smart_retry_recovered_inr: number;
  incremental_inr: number;
  baseline_recovery_rate: number;
  smart_retry_recovery_rate: number;
}

export interface ConfidenceResponse {
  tiers: ConfidenceTierStats[];
}

export interface PredictionCandidateScore {
  candidate_retry_hours: number;
  calibrated_probability: number;
  confidence_tier: "Low" | "Medium" | "High";
}

export interface PredictResponse {
  eligible: boolean;
  selected_retry_hours: number;
  calibrated_probability: number;
  confidence_tier: "Low" | "Medium" | "High";
  candidate_scores: PredictionCandidateScore[];
}

export interface SimulateResponse {
  transaction_id: string;
  selected_retry_hours: number;
  probability: number;
  confidence: "High" | "Medium" | "Low";
  simulated_result: "recovered" | "lost" | "prediction_only_no_observed_synthetic_outcome";
  recovered_inr: number;
  stopping_reason: string;
  audit_events: AuditEvent[];
}

export interface AuditEvent {
  event: string;
  timestamp: string | null;
  timestamp_note?: string | null;
  selected_schedule_hours?: number | null;
  selected_retry_hours?: number | null;
  calibrated_probability?: number | null;
  confidence_tier?: string | null;
  recovered?: boolean | null;
  simulated?: boolean | null;
}

export interface AuditResponse {
  transaction_id: string;
  events: AuditEvent[];
}

export interface TransactionsResponse {
  page: number;
  page_size: number;
  total: number;
  items: Array<Record<string, number | string | boolean | null>>;
}

export interface TransactionContext {
  amount_inr: number;
  decline_reason: string;
  payment_method: string;
  hour_of_day: number;
  day_of_month: number;
  day_of_week: number;
  customer_previous_success_rate: number;
  customer_previous_failure_count: number;
  days_since_last_successful_payment: number;
  transaction_id?: string;
  failed_at?: string;
  customer_prior_failures?: number;
  customer_prior_recoveries?: number;
}

export interface DatasetValidationResult {
  valid: boolean;
  record_count: number;
  eligible_count?: number | null;
  errors: string[];
  warnings: string[];
}

export interface InferenceResultItem {
  transaction_id?: string | null;
  customer_id?: string | null;
  eligible: boolean;
  selected_retry_hours?: number | null;
  calibrated_probability?: number | null;
  confidence_tier?: "Low" | "Medium" | "High" | null;
  error?: string | null;
}

export interface InferenceResponse {
  dataset_source: "demo" | "upload";
  total_records: number;
  eligible_records: number;
  processed_records: number;
  failed_records: number;
  eligible_by_confidence: Record<string, number>;
  avg_selected_retry_hours?: number | null;
  results: InferenceResultItem[];
  errors: string[];
}
