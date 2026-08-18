import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  icon: LucideIcon;
  accent?: string;
  positive?: boolean;
  negative?: boolean;
  loading?: boolean;
}

export function StatCard({ label, value, sub, icon: Icon, accent, positive, negative, loading }: StatCardProps) {
  const subColor = negative
    ? "text-[#d91536]"
    : positive
      ? "text-[#146e5a]"
      : "text-[#545b64]";
  return (
    <Card className="relative overflow-hidden rounded-[4px] border border-[#eaeded] bg-white shadow-[0_1px_3px_0_rgba(0,0,0,.3),0_0_0_1px_rgba(0,0,0,.04)]">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-[12px] font-bold uppercase tracking-wider text-[#545b64]">{label}</p>
            {loading ? (
              <div className="mt-2 h-7 w-24 animate-pulse rounded bg-[#f9f9fb]" />
            ) : (
              <p className="mt-1 text-[24px] font-bold tracking-tight text-[#232f3e]">{value}</p>
            )}
            {sub && (
              <p className={cn("mt-1 truncate text-[12px] font-bold", subColor)}>{sub}</p>
            )}
          </div>
          <div
            className="grid h-9 w-9 shrink-0 place-items-center rounded-[4px]"
            style={{ backgroundColor: accent ? `${accent}12` : undefined }}
          >
            <Icon className="h-5 w-5" style={accent ? { color: accent } : undefined} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
