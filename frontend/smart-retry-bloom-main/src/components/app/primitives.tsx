import type { ReactNode } from "react";
import { AlertTriangle, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import type { ConfidenceTier, RetryResult } from "@/lib/api/types";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        {eyebrow && (
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
            {eyebrow}
          </p>
        )}
        <h1 className="mt-2 text-3xl font-semibold text-foreground lg:text-[38px]">{title}</h1>
        {description && (
          <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">{description}</p>
        )}
      </div>
      {actions}
    </div>
  );
}

export function Panel({
  title,
  description,
  children,
  className,
  action,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <section className={cn("surface p-6", className)}>
      {(title || action) && (
        <header className="mb-5 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-base font-semibold text-foreground">{title}</h2>}
            {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function KpiCard({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "mint" | "lavender" | "peach" | "sky" | "rose";
}) {
  const tones: Record<string, string> = {
    neutral: "bg-card",
    mint: "bg-mint-soft",
    lavender: "bg-lavender-soft",
    peach: "bg-peach-soft",
    sky: "bg-sky-soft",
    rose: "bg-rose-soft",
  };
  return (
    <div className={cn("surface p-5", tones[tone])}>
      <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-3 font-display text-[26px] font-semibold leading-none text-foreground">
        {value}
      </p>
      {sub && <p className="mt-2 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export function LoadingBlock({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full rounded-xl" />
      ))}
    </div>
  );
}

export function ErrorBlock({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="surface flex flex-col items-start gap-3 bg-rose-soft p-6">
      <span className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
        <AlertTriangle className="size-4 text-rose" /> Couldn't load data
      </span>
      <p className="text-xs text-muted-foreground">
        {message ?? "The recovery API did not respond. Check VITE_API_BASE_URL and try again."}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
        >
          Retry request
        </button>
      )}
    </div>
  );
}

export function EmptyBlock({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border py-12 text-center">
      <Inbox className="size-5 text-muted-foreground" />
      <p className="text-xs text-muted-foreground">{message}</p>
    </div>
  );
}

const tierStyles: Record<ConfidenceTier, string> = {
  high: "bg-mint-soft text-foreground",
  medium: "bg-amber-soft text-foreground",
  low: "bg-rose-soft text-foreground",
};

export function ConfidencePill({ tier }: { tier: ConfidenceTier }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[11px] font-medium capitalize",
        tierStyles[tier],
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          tier === "high" ? "bg-mint" : tier === "medium" ? "bg-amber" : "bg-rose",
        )}
      />
      {tier} confidence
    </span>
  );
}

const resultStyles: Record<RetryResult, string> = {
  recovered: "bg-mint-soft",
  stopped: "bg-amber-soft",
  failed: "bg-rose-soft",
  pending: "bg-sky-soft",
};

export function ResultPill({ result }: { result: RetryResult }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full border border-border px-2.5 py-1 text-[11px] font-medium capitalize text-foreground",
        resultStyles[result],
      )}
    >
      {result}
    </span>
  );
}
