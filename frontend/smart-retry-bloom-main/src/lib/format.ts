export function formatInr(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `${value < 0 ? "−" : ""}₹${(Math.abs(value) / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${value < 0 ? "−" : ""}₹${(Math.abs(value) / 1_000).toFixed(1)}K`;
  }
  return `${value < 0 ? "−" : ""}₹${Math.abs(value).toFixed(0)}`;
}

export function formatInrFull(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value);
}

export function formatPct(value: number, digits = 2): string {
  return `${value.toFixed(digits)}%`;
}

export function formatSignedPct(value: number, digits = 2): string {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}%`;
}

export function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
