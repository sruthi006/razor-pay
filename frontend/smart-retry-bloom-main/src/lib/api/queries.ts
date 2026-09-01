import { queryOptions } from "@tanstack/react-query";
import { api } from "./client";

export const dashboardQuery = queryOptions({
  queryKey: ["dashboard"],
  queryFn: api.getDashboard,
});

export const businessImpactQuery = queryOptions({
  queryKey: ["business-impact"],
  queryFn: api.getBusinessImpact,
});

export const recoveryBreakdownQuery = (dimension: string) =>
  queryOptions({
    queryKey: ["recovery-breakdown", dimension],
    queryFn: () => api.getRecoveryBreakdown(dimension),
    enabled: !!dimension,
  });

export const retryDistributionQuery = queryOptions({
  queryKey: ["retry-distribution"],
  queryFn: api.getRetryDistribution,
});

export const confidenceQuery = queryOptions({
  queryKey: ["confidence"],
  queryFn: api.getConfidence,
});

export const auditQuery = (transactionId: string) =>
  queryOptions({
    queryKey: ["audit", transactionId],
    queryFn: () => api.getAudit(transactionId),
    enabled: !!transactionId,
  });

export const transactionsQuery = queryOptions({
  queryKey: ["transactions"],
  queryFn: () => api.getTransactions(1, 25),
});

// Inference mutations (not queries because they depend on user input)
export const uploadAndInferMutation = {
  mutationFn: (file: File) => api.uploadAndInfer(file),
};

export const loadDemoDatasetMutation = {
  mutationFn: () => api.loadDemoDataset(),
};

export const validateCsvMutation = {
  mutationFn: (file: File) => api.validateCsv(file),
};
