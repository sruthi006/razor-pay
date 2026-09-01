import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { BreakdownChart, RetryDistributionChart } from "@/components/app/charts";
import { ErrorBlock, KpiCard, LoadingBlock, PageHeader, Panel } from "@/components/app/primitives";
import {
  businessImpactQuery,
  recoveryBreakdownQuery,
  retryDistributionQuery,
} from "@/lib/api/queries";
import { normalizeBreakdownRows, normalizeRetryDistribution } from "@/lib/api/client";
import { formatInr, formatPct } from "@/lib/format";

export const Route = createFileRoute("/business-impact")({
  head: () => ({
    meta: [
      { title: "Business Impact — Smart Retry" },
      {
        name: "description",
        content:
          "Simulated revenue impact of AI-timed payment retries: incremental revenue, lift, and breakdowns by decline reason, method and amount band.",
      },
      { property: "og:title", content: "Business Impact — Smart Retry" },
      {
        property: "og:description",
        content:
          "Simulated revenue impact of AI-timed payment retries, with breakdowns by decline reason, payment method and amount band.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: BusinessImpact,
});

function BusinessImpact() {
  const impact = useQuery(businessImpactQuery);
  const declineBreakdown = useQuery(recoveryBreakdownQuery("decline_reason"));
  const paymentBreakdown = useQuery(recoveryBreakdownQuery("payment_method"));
  const amountBreakdown = useQuery(recoveryBreakdownQuery("amount_band"));
  const distribution = useQuery(retryDistributionQuery);

  const fixed = impact.data?.fixed_schedule ?? {};
  const smart = impact.data?.smart_retry ?? {};
  const incremental = impact.data?.incremental ?? {};

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Business impact"
        title="What smarter retry timing is worth"
        description="Side-by-side simulated outcomes for a fixed retry schedule and the Smart Retry policy."
      />

      {impact.isLoading && <LoadingBlock rows={4} />}
      {impact.isError && (
        <ErrorBlock message="Could not load business impact." onRetry={() => impact.refetch()} />
      )}
      {impact.data && (
        <>
          {!impact.data.outcome_data_available ? (
            <Panel title="Outcome metrics unavailable" description={impact.data.outcome_unavailable_message ?? impact.data.limitations[0] ?? "The selected dataset contains inference inputs only."} />
          ) : <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Fixed schedule"
              value={formatInr(Number(fixed.recovered_inr ?? 0))}
              sub={`${formatPct(Number(fixed.recovery_rate ?? 0) * 100, 1)} recovery rate`}
              tone="peach"
            />
            <KpiCard
              label="Smart Retry"
              value={formatInr(Number(smart.recovered_inr ?? 0))}
              sub={`${formatPct(Number(smart.recovery_rate ?? 0) * 100, 1)} recovery rate`}
              tone="mint"
            />
            <KpiCard
              label="Incremental revenue"
              value={formatInr(Number(incremental.recovered_inr ?? 0))}
              tone="lavender"
            />
            <KpiCard
              label="Lift"
              value={formatPct(Number(incremental.recovered_inr_lift_pct ?? 0) * 100, 1)}
              tone="sky"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {impact.data.limitations.length > 0
              ? impact.data.limitations[0]
              : "Results are from the validated synthetic evaluation artifacts."}
          </p>
          </>}
        </>
      )}

      {impact.data?.outcome_data_available && <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="By decline reason" description="Recovered value per failure category.">
          {declineBreakdown.isLoading && <LoadingBlock rows={4} />}
          {declineBreakdown.isError && (
            <ErrorBlock
              message="Could not load breakdown."
              onRetry={() => declineBreakdown.refetch()}
            />
          )}
          {declineBreakdown.data && (
            <BreakdownChart rows={normalizeBreakdownRows(declineBreakdown.data)} />
          )}
        </Panel>
        <Panel title="By payment method" description="Recovered value per instrument type.">
          {paymentBreakdown.data && (
            <BreakdownChart rows={normalizeBreakdownRows(paymentBreakdown.data)} height={280} />
          )}
        </Panel>
        <Panel title="By amount band" description="Recovered value per ticket size.">
          {amountBreakdown.data && (
            <BreakdownChart rows={normalizeBreakdownRows(amountBreakdown.data)} height={280} />
          )}
        </Panel>
        <Panel
          title="Selected retry timing"
          description="How often each retry offset is chosen, and how it performs."
        >
          {distribution.isLoading && <LoadingBlock rows={4} />}
          {distribution.isError && (
            <ErrorBlock
              message="Could not load retry distribution."
              onRetry={() => distribution.refetch()}
            />
          )}
          {distribution.data && (
            <RetryDistributionChart buckets={normalizeRetryDistribution(distribution.data)} />
          )}
        </Panel>
      </div>}
    </div>
  );
}
