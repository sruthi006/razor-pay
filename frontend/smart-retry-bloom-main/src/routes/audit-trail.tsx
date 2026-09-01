import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  ConfidencePill,
  EmptyBlock,
  ErrorBlock,
  LoadingBlock,
  PageHeader,
  Panel,
  ResultPill,
} from "@/components/app/primitives";
import { auditQuery, transactionsQuery } from "@/lib/api/queries";
import { formatInr, formatTimestamp } from "@/lib/format";

export const Route = createFileRoute("/audit-trail")({
  head: () => ({
    meta: [
      { title: "Audit Trail — Smart Retry" },
      {
        name: "description",
        content:
          "Step-by-step decision log for every simulated retry: eligibility, scoring, recommendation, confidence and bounded action.",
      },
      { property: "og:title", content: "Audit Trail — Smart Retry" },
      {
        property: "og:description",
        content:
          "Step-by-step decision log for every simulated retry, from eligibility check to bounded recovery action.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AuditTrail,
});

function AuditTrail() {
  const transactions = useQuery(transactionsQuery);
  const transactionId = transactions.data?.items[0]?.transaction_id ?? "TX000001";
  const audit = useQuery(auditQuery(String(transactionId)));
  const [openId, setOpenId] = useState<string | null>(null);

  const auditEvents = audit.data?.events ?? [];
  const summary = auditEvents.length
    ? [{
        id: audit.data?.transaction_id ?? transactionId,
        transaction_id: audit.data?.transaction_id ?? transactionId,
        decline_reason: "Decision audit",
        selected_offset_label: auditEvents[0]?.selected_retry_hours ?? "n/a",
        confidence_tier: (auditEvents[0]?.confidence_tier ?? "Low").toLowerCase() as "low" | "medium" | "high",
        result: auditEvents.some((event) => event.recovered) ? "recovered" : "stopped",
        recovered_amount_inr: 0,
        timestamp: auditEvents[0]?.timestamp ?? new Date().toISOString(),
        events: auditEvents.map((event, index) => ({
          step: event.event,
          timestamp: event.timestamp ?? new Date().toISOString(),
          detail: event.timestamp_note ?? `${event.event} evaluated in the synthetic audit trail.`,
        })),
      }]
    : [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Audit trail"
        title="Every decision is explainable"
        description="Each simulated retry records the full decision chain so a reviewer can reconstruct why the agent acted."
      />

      <Panel title="Decision records" description="Newest simulated decisions first.">
        {transactions.isLoading || (audit.isLoading && !audit.data) ? <LoadingBlock rows={6} /> : null}
        {audit.isError && (
          <ErrorBlock message="Could not load the audit trail." onRetry={() => audit.refetch()} />
        )}
        {audit.data && summary.length === 0 && <EmptyBlock message="No decision records yet." />}
        {summary.length > 0 && (
          <div className="divide-y divide-border">
            {summary.map((record) => {
              const open = openId === record.id;
              return (
                <div key={record.id} className="py-3">
                  <button
                    type="button"
                    onClick={() => setOpenId(open ? null : record.id)}
                    className="flex w-full flex-wrap items-center gap-3 text-left"
                  >
                    <span className="font-mono text-xs text-muted-foreground">
                      {record.transaction_id}
                    </span>
                    <span className="text-sm text-foreground">{record.decline_reason}</span>
                    <span className="text-xs text-muted-foreground">
                      retry {record.selected_offset_label}
                    </span>
                    <ConfidencePill tier={record.confidence_tier} />
                    <ResultPill result={record.result} />
                    <span className="ml-auto text-xs text-muted-foreground">
                      {formatTimestamp(record.timestamp)}
                    </span>
                    <span className="text-sm font-medium text-foreground">
                      {formatInr(record.recovered_amount_inr)}
                    </span>
                  </button>

                  {open && (
                    <ol className="mt-4 space-y-3 border-l border-border pl-5">
                      {record.events.map((event, i) => (
                        <li key={`${record.id}-${i}`} className="relative">
                          <span className="absolute -left-[23px] top-1.5 size-2 rounded-full bg-primary" />
                          <p className="text-sm font-medium text-foreground">{event.step}</p>
                          <p className="text-xs text-muted-foreground">{event.detail}</p>
                          <p className="text-[11px] text-muted-foreground">
                            {formatTimestamp(event.timestamp)}
                          </p>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
