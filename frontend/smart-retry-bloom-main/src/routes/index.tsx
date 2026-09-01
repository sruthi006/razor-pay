import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ComparisonBarChart, RecoveryRateChart } from "@/components/app/charts";
import {
  ErrorBlock,
  EmptyBlock,
  KpiCard,
  LoadingBlock,
  PageHeader,
  Panel,
} from "@/components/app/primitives";
import { dashboardQuery, confidenceQuery } from "@/lib/api/queries";
import { formatInr, formatNumber, formatPct } from "@/lib/format";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Smart Retry — AI Revenue Recovery Command Center" },
      {
        name: "description",
        content:
          "Simulated command center comparing fixed-schedule retries with AI-timed Smart Retry recovery on failed payments.",
      },
      { property: "og:title", content: "Smart Retry — AI Revenue Recovery Command Center" },
      {
        property: "og:description",
        content:
          "Simulated command center comparing fixed-schedule retries with AI-timed Smart Retry recovery on failed payments.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  const dashboard = useQuery(dashboardQuery);
  const confidence = useQuery(confidenceQuery);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Command center"
        title="Recover revenue lost to failed payments"
        description="Smart Retry scores every failed payment, picks the retry moment with the highest calibrated success probability, and stops low-confidence retries. All figures below come from a synthetic policy simulation."
      />

      {dashboard.isLoading && <LoadingBlock rows={4} />}
      {dashboard.isError && (
        <ErrorBlock message="Could not load dashboard metrics." onRetry={() => dashboard.refetch()} />
      )}

      {dashboard.data && (
        <>
          <Panel title="Data Source" description="">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Source:</span>
                <span className="font-medium">{dashboard.data.dataset_source === "upload" ? "Selected uploaded CSV" : "Validated demo evaluation dataset"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Model:</span>
                <span className="font-medium">Existing trained model (not retrained)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Available metrics:</span>
                <span className="font-medium">{dashboard.data.outcome_data_available ? "Observed-outcome policy comparison" : "Inference recommendations"}</span>
              </div>
            </div>
          </Panel>

          {!dashboard.data.outcome_data_available && (
            <Panel title="Outcome metrics unavailable" description={dashboard.data.outcome_unavailable_message ?? "This dataset contains inference inputs only."} />
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Failed payments"
              value={formatNumber(dashboard.data.total_failed_transactions)}
              sub={`${formatNumber(dashboard.data.eligible_transactions)} eligible for retry`}
              tone="sky"
            />
            <KpiCard
              label={dashboard.data.outcome_data_available ? "Fixed schedule recovered" : "Recommendations processed"}
              value={dashboard.data.outcome_data_available ? formatInr(dashboard.data.fixed_recovered_inr) : formatNumber(dashboard.data.eligible_transactions)}
              sub={dashboard.data.outcome_data_available ? "Baseline policy" : "Eligible for Smart Retry"}
              tone="peach"
            />
            <KpiCard
              label={dashboard.data.outcome_data_available ? "Smart Retry recovered" : "Outcome data"}
              value={dashboard.data.outcome_data_available ? formatInr(dashboard.data.smart_recovered_inr) : "Unavailable"}
              sub={dashboard.data.outcome_data_available ? "AI-timed bounded retries" : "No observed retry outcomes"}
              tone="mint"
            />
            <KpiCard
              label={dashboard.data.outcome_data_available ? "Incremental revenue" : "Model"}
              value={dashboard.data.outcome_data_available ? formatInr(dashboard.data.incremental_recovered_inr) : "Unchanged"}
              sub={dashboard.data.outcome_data_available ? `${formatPct(dashboard.data.recovered_value_lift_percent, 1)} lift` : "Existing trained model"}
              tone="lavender"
            />
          </div>

          {dashboard.data.outcome_data_available && <div className="grid gap-6 xl:grid-cols-2">
            <Panel
              title="Recovered revenue by strategy"
              description="Simulated recovered value, fixed schedule vs Smart Retry."
            >
              <ComparisonBarChart
                data={[
                  {
                    label: "Recovered value",
                    fixed: dashboard.data.fixed_recovered_inr,
                    smart: dashboard.data.smart_recovered_inr,
                  },
                ]}
              />
            </Panel>
            <Panel
              title="Recovery rate by strategy"
              description="Share of eligible failed payments recovered."
            >
              <RecoveryRateChart
                data={[
                  {
                    label: "Recovery rate",
                    fixed: dashboard.data.fixed_recovery_rate * 100,
                    smart: dashboard.data.smart_recovery_rate * 100,
                  },
                ]}
              />
            </Panel>
          </div>}
        </>
      )}

      <Panel
        title="Confidence-tier behaviour"
        description={
          !dashboard.data?.outcome_data_available
            ? "Recommendation counts are available, but confidence-tier revenue impact requires observed outcomes."
            : confidence.data?.tiers.length
            ? `High-confidence retries are the main driver of the uplift; low-confidence cases are held back by the bounded policy.`
            : "How the agent behaves across confidence tiers."
        }
      >
        {confidence.isLoading && <LoadingBlock rows={3} />}
        {confidence.isError && (
          <ErrorBlock message="Could not load confidence tiers." onRetry={() => confidence.refetch()} />
        )}
        {!dashboard.data?.outcome_data_available && <EmptyBlock message="Confidence-tier revenue metrics are unavailable for inference-only data." />}
        {dashboard.data?.outcome_data_available && confidence.data && (
          <div className="grid gap-4 sm:grid-cols-3">
            {confidence.data.tiers.map((t) => (
              <div key={t.smart_retry_confidence} className="rounded-xl border border-border bg-card p-4">
                <p className="text-sm font-semibold text-foreground">
                  {t.smart_retry_confidence.toLowerCase()} confidence
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatNumber(t.eligible_transactions)} transactions
                </p>
                <p className="mt-3 font-display text-xl font-semibold text-foreground">
                  {formatInr(t.incremental_inr)}
                </p>
                <p className="text-xs text-muted-foreground">incremental vs baseline</p>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
