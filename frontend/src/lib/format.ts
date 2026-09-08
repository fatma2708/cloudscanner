export function formatCurrency(value: number | undefined | null, digits = 0): string {
  const n = Number(value ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

export function formatCompactCurrency(value: number | undefined | null): string {
  const n = Number(value ?? 0);
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(n / 1_000).toFixed(1)}k`;
  return `$${n.toFixed(0)}`;
}

export function formatPercent(value: number | undefined | null, digits = 1): string {
  return `${(Number(value ?? 0)).toFixed(digits)}%`;
}

export function formatConfidence(value: number | undefined | null): string {
  const n = Number(value ?? 0);
  const pct = Math.round(n * 1000) / 10;
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`;
}

export function formatNumber(value: number | undefined | null, digits = 0): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(Number(value ?? 0));
}

export function formatKg(value: number | undefined | null, digits = 1): string {
  return `${(Number(value ?? 0)).toFixed(digits)} kg`;
}

export function formatDate(iso: string | undefined | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
