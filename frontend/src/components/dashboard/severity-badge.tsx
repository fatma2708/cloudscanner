import { Badge } from "@/components/ui/badge";
import type { Severity } from "@/lib/types";

const STYLES: Record<Severity, string> = {
  critical: "border-red-500/30 bg-red-500/10 text-red-400",
  high: "border-orange-500/30 bg-orange-500/10 text-orange-400",
  medium: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  low: "border-sky-500/30 bg-sky-500/10 text-sky-300",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant="outline" className={STYLES[severity]}>
      {severity}
    </Badge>
  );
}
