import { Link } from "@tanstack/react-router";
import { Activity, BarChart3, ScrollText, Sparkles, LayoutDashboard, Upload } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { USING_MOCK_DATA } from "@/lib/api/client";

const NAV = [
  { to: "/dataset-selection", label: "Select Dataset", icon: Upload },
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/recovery-agent", label: "Recovery Agent", icon: Sparkles },
  { to: "/business-impact", label: "Business Impact", icon: BarChart3 },
  { to: "/audit-trail", label: "Audit Trail", icon: ScrollText },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen page-canvas">
      <div className="mx-auto flex min-h-screen w-full max-w-[1600px]">
        <aside className="sticky top-0 hidden h-screen w-[264px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar/70 px-5 py-7 backdrop-blur-sm lg:flex">
          <BrandMark />
          <nav className="mt-9 flex flex-col gap-1">
            {NAV.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                activeOptions={{ exact: to === "/" }}
                className="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                activeProps={{
                  className: "bg-accent text-accent-foreground shadow-[var(--shadow-soft)]",
                }}
              >
                <Icon className="size-4" strokeWidth={1.9} />
                {label}
              </Link>
            ))}
          </nav>
          <div className="mt-auto rounded-xl border border-border bg-card p-4">
            <p className="text-xs font-semibold text-foreground">Prototype notice</p>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
              Smart Retry is a decision-simulation prototype. It is not connected to any live
              payment gateway.
            </p>
            <p className="mt-2 text-[11px] text-muted-foreground">
              Data source:{" "}
              <span className="font-medium text-foreground">
                {USING_MOCK_DATA ? "Mock service layer" : "FastAPI backend"}
              </span>
            </p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-border bg-background/80 px-6 py-4 backdrop-blur-md lg:px-10">
            <div className="lg:hidden">
              <BrandMark compact />
            </div>
            <nav className="flex gap-1 overflow-x-auto lg:hidden">
              {NAV.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  activeOptions={{ exact: to === "/" }}
                  className="whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
                  activeProps={{ className: "bg-accent text-accent-foreground" }}
                >
                  {label}
                </Link>
              ))}
            </nav>
            <div className="ml-auto flex items-center gap-3">
              <StatusIndicator />
            </div>
          </header>

          <main className="flex-1 px-6 py-8 lg:px-10 lg:py-10">{children}</main>

          <footer className="border-t border-border px-6 py-5 text-xs text-muted-foreground lg:px-10">
            Smart Retry — synthetic-data policy simulation. Figures shown are simulated outcomes,
            not production payment performance.
          </footer>
        </div>
      </div>
    </div>
  );
}

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-3">
      <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
        <Activity className="size-5" strokeWidth={2.1} />
      </span>
      <span className="leading-tight">
        <span className="block font-display text-[15px] font-semibold text-foreground">
          Smart Retry
        </span>
        {!compact && (
          <span className="block text-[11px] text-muted-foreground">AI Revenue Recovery Agent</span>
        )}
      </span>
    </Link>
  );
}

export function StatusIndicator({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-border bg-amber-soft px-3 py-1.5 text-[11px] font-medium text-foreground",
        className,
      )}
    >
      <span className="relative flex size-1.5">
        <span className="absolute inline-flex size-full rounded-full bg-amber opacity-70" />
      </span>
      Simulation Environment
    </span>
  );
}
