import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ConfidencePill,
  ErrorBlock,
  LoadingBlock,
  PageHeader,
  Panel,
} from "@/components/app/primitives";
import { api } from "@/lib/api/client";
import { transactionsQuery } from "@/lib/api/queries";
import type { PredictResponse, TransactionContext } from "@/lib/api/types";
import { formatInr, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export const Route = createFileRoute("/recovery-agent")({
  head: () => ({
    meta: [
      { title: "Recovery Agent — Smart Retry" },
      {
        name: "description",
        content:
          "Pick a failed payment and watch the agent score retry windows, recommend the best time, and show confidence.",
      },
      { property: "og:title", content: "Recovery Agent — Smart Retry" },
      {
        property: "og:description",
        content:
          "Score retry windows, recommend the best retry time based on ML confidence, and display the decision.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: RecoveryAgent,
});

function RecoveryAgent() {
  const transactions = useQuery(transactionsQuery);
  const [selected, setSelected] = useState<TransactionContext | null>(null);
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);

  const predictMutation = useMutation({
    mutationFn: (ctx: TransactionContext) => api.predict(ctx),
    onSuccess: (data) => {
      setPrediction(data);
    },
    onError: (error) => {
      toast.error(`Prediction failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setPrediction(null);
    },
  });

  function choose(ctx: TransactionContext) {
    setSelected(ctx);
    setPrediction(null);
    predictMutation.mutate(ctx);
  }

  const chartData =
    prediction?.candidate_scores.map((score) => ({
      hours: score.candidate_retry_hours,
      probability: (score.calibrated_probability * 100).toFixed(1),
      tier: score.confidence_tier,
    })) ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Recovery agent"
        title="Analyze a failed payment"
        description="Select a transaction to see how the model scores different retry windows, recommends the best time, and assigns confidence."
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <Panel title="Failed payments" description="Select a transaction to analyze.">
          {transactions.isLoading && <LoadingBlock rows={6} />}
          {transactions.isError && (
            <ErrorBlock
              message="Could not load transactions."
              onRetry={() => transactions.refetch()}
            />
          )}
          {transactions.data?.items && (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {transactions.data.items.map((t, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => choose(t as TransactionContext)}
                  className={cn(
                    "w-full rounded-xl border border-border bg-card p-3 text-left transition-colors hover:bg-accent",
                    selected?.transaction_id === (t as TransactionContext).transaction_id && "border-primary bg-accent",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {(t as TransactionContext).transaction_id || `TXN_${idx}`}
                    </span>
                    <span className="text-sm font-semibold text-foreground">
                      {formatInr((t as TransactionContext).amount_inr)}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-foreground">
                    {(t as TransactionContext).decline_reason}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {(t as TransactionContext).payment_method}
                  </p>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <div className="space-y-6">
          {!selected && (
            <Panel>
              <p className="text-sm text-muted-foreground">
                Select a failed payment to see the model's decision.
              </p>
            </Panel>
          )}

          {selected && predictMutation.isPending && (
            <Panel title="Analyzing">
              <LoadingBlock rows={4} />
            </Panel>
          )}

          {selected && prediction && (
            <>
              <Panel title="Model Decision">
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground">Eligibility</p>
                      <p className="mt-2 text-lg font-bold text-foreground">
                        {prediction.eligible ? "✓ Eligible" : "✗ Not eligible"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground">Confidence</p>
                      <div className="mt-2">
                        <ConfidencePill tier={prediction.confidence_tier} />
                      </div>
                    </div>
                  </div>

                  {prediction.eligible && (
                    <>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <p className="text-xs font-semibold text-muted-foreground">
                            Recommended retry offset
                          </p>
                          <p className="mt-2 text-2xl font-bold text-primary">
                            {prediction.selected_retry_hours.toFixed(2)}h
                          </p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-muted-foreground">
                            Calibrated success probability
                          </p>
                          <p className="mt-2 text-2xl font-bold text-mint">
                            {formatPct(prediction.calibrated_probability * 100, 1)}
                          </p>
                        </div>
                      </div>

                      <p className="text-xs text-muted-foreground">
                        The model evaluated 10 candidate retry offsets and selected {prediction.selected_retry_hours.toFixed(2)} hours as the time with the highest calibrated success probability.
                      </p>
                    </>
                  )}
                </div>
              </Panel>

              {prediction.eligible && prediction.candidate_scores.length > 0 && (
                <Panel
                  title="All candidate retry times"
                  description="Model score for each possible retry offset"
                >
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="hours" />
                        <YAxis />
                        <Tooltip 
                          formatter={(value) => `${value}%`}
                          contentStyle={{ 
                            backgroundColor: "hsl(var(--card))",
                            border: "1px solid hsl(var(--border))",
                            borderRadius: "0.5rem"
                          }}
                        />
                        <Bar 
                          dataKey="probability" 
                          fill="hsl(var(--primary))"
                          name="Success probability (%)"
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="mt-6 space-y-2">
                    {prediction.candidate_scores.map((score, idx) => (
                      <div
                        key={idx}
                        className={cn(
                          "flex items-center justify-between rounded-lg border border-border p-2",
                          score.candidate_retry_hours === prediction.selected_retry_hours &&
                            "border-primary bg-primary/5",
                        )}
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-mono font-medium">
                            {score.candidate_retry_hours.toFixed(2)}h
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {formatPct(score.calibrated_probability * 100, 1)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {score.candidate_retry_hours === prediction.selected_retry_hours && (
                            <span className="text-xs font-semibold text-primary">SELECTED</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </Panel>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
